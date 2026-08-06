"""matplotlib backend — FigureCanvasQTAgg wrapper + RenderHandle (spec §4.2)."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_API", "pyside6")  # bind matplotlib's Qt to PySide6

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ...core._degrade import FULL_SURFACE, check_layout, check_recommended, check_surface
from ...core.backend import (
    PaneHandle,
    RenderContext,
    RendererRegistry,
    RenderHandle,
    ViewState,
)
from ...core.capabilities import Capabilities
from ...core.compose import (
    Layout,
    Overlay,
    effective_scales,
    series_index_map,
    surface_of,
)
from ...core.element import Element
from ...core.event import EventBus, PaneBus
from ...core.threading import require_gui_thread
from ...data import resolve_node
from ...errors import RendererMissingError
from . import _events
from ._renderers import HONORED_DELTAS, RENDERERS
from ._surface import apply_surface
from ._theme import apply_theme_ax, apply_theme_fig

_CAPS = Capabilities(
    dimensions=frozenset({2}),  # honest: no 3-D renderer exists ([D52]); was aspirational {2,3}
    opengl=False,
    picking="native",
    brush="approximate",
    range_events=True,
    streaming=False,
    max_recommended_points=100_000,
    animation=False,  # honest: no animation API ([D52], §12 out of scope)
    exports=frozenset({"png", "svg", "pdf"}),
    threading_model="gui_only",
    # mpl transforms data itself and keeps get_xlim() in data space — no R1 work;
    # symlog is the mpl-only scale that exercises the capability gate ([D59]).
    scales=frozenset({"linear", "log", "symlog", "time"}),  # time: [D94]
)


class MplPane(PaneHandle):
    """One `Axes` of the figure ([D147]). matplotlib keeps `get_xlim()` in data
    space under any scale, so capture/restore need no R1 normalization."""

    def __init__(self, label: str, fig, surf: dict, bus) -> None:
        super().__init__(label)
        self._fig = fig
        self._surf = surf
        self._bus = bus

    def capture(self) -> ViewState:
        self._assert_alive()
        ax, ax2 = self._surf["ax"], self._surf.get("y2_ax")
        return ViewState(x_range=tuple(ax.get_xlim()), y_range=tuple(ax.get_ylim()),
                         y2_range=tuple(ax2.get_ylim()) if ax2 is not None else None)

    @require_gui_thread
    def restore(self, state: ViewState) -> None:
        self._assert_alive()
        ax = self._surf["ax"]
        if state.x_range:
            ax.set_xlim(*state.x_range)
        if state.y_range:
            ax.set_ylim(*state.y_range)
        if state.y2_range and self._surf.get("y2_ax") is not None:
            self._surf["y2_ax"].set_ylim(*state.y2_range)
        self._fig.canvas.draw_idle()

    @require_gui_thread
    def autorange(self) -> None:
        self._assert_alive()
        for a in (self._surf["ax"], self._surf.get("y2_ax")):
            if a is not None:
                a.relim()
                a.autoscale()
        self._fig.canvas.draw_idle()

    @require_gui_thread
    def select(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self._assert_alive()
        _events.emit_bounds_select(self._surf["selectables"], self._bus, x0, y0, x1, y1)

    @property
    def native(self):
        return self._surf["ax"]

    @property
    def elements(self) -> tuple[str, ...]:
        return tuple(self._surf.get("element_ids", ()))

    @require_gui_thread
    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        """One pane in any mpl format — the figure cropped to this axes' tight
        bbox (spiked; [D150]). The crop is geometric: an artist overhanging
        the axes region (a neighbor's wide legend) can intrude at the margin."""
        self._assert_alive()
        path = Path(path)
        fig = self._fig
        fig.canvas.draw()  # tightbbox needs a live renderer
        bbox = (self._surf["ax"].get_tightbbox()
                .transformed(fig.dpi_scale_trans.inverted()))
        kw: dict = {"format": fmt, "transparent": transparent, "bbox_inches": bbox}
        if dpi is not None:
            kw["dpi"] = dpi
        fig.savefig(str(path), **kw)
        return path


class MplRenderHandle(RenderHandle):
    def __init__(self, canvas, fig, bus, surfaces, root, backend, natives) -> None:
        super().__init__(canvas, bus, "matplotlib")
        self._fig = fig
        self._surfaces = surfaces  # [{"ax", "surface_id", "selectables", "y2_ax", "element_ids"}]
        self._root = root
        self._backend = backend
        self._natives = natives  # element id → mpl Artist ([D53])

    @property
    def axes(self):
        return [s["ax"] for s in self._surfaces]

    def _panes(self) -> tuple[MplPane, ...]:
        from ...core.compose import flat_pane_labels  # noqa: PLC0415

        labels = flat_pane_labels(self._root)  # [D145] given labels, else indices
        if len(labels) != len(self._surfaces):  # defensive: identity never crashes
            labels = tuple(str(i) for i in range(len(self._surfaces)))
        return tuple(MplPane(lb, self._fig, s, s.get("bus", self.event_bus))
                     for lb, s in zip(labels, self._surfaces, strict=True))

    def select_bounds(self, ax_index: int, xmin, ymin, xmax, ymax) -> None:
        """Programmatic brush (approximate) — emits one SelectEvent per
        selectable element on the axes (element id + indices + bounds); the
        interactive rubber band ([D95]) drives the same helper."""
        surf = self._surfaces[ax_index]
        _events.emit_bounds_select(surf["selectables"],
                                   surf.get("bus", self.event_bus),
                                   xmin, ymin, xmax, ymax)

    @require_gui_thread
    def set_element_data(self, element_id: str, arrays: dict) -> bool:
        """Streaming rung 1 for datashaded elements ([D77] ladder): their live
        ref already holds the new rows, so a viewport re-aggregation through
        the RasterController is the in-place update — matplotlib's only fast
        path (plain artists still rebuild; `streaming=False` stays honest)."""
        for s in self._surfaces:
            for controller in getattr(s["ax"], "_qtviz_rasters", ()):
                if getattr(controller, "element_id", None) == element_id:
                    controller.refresh()
                    return True
        return False

    def toolbar(self):
        """matplotlib's navigation toolbar ([D95]) — mouse pan/zoom for the
        static backend; limit changes flow into RangeEvents as usual."""
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT  # noqa: PLC0415

        return NavigationToolbar2QT(self.widget, None)

    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        path = Path(path)
        kw: dict = {"format": fmt, "transparent": transparent}
        if dpi is not None:
            kw["dpi"] = dpi  # export knobs ([D72]); mpl honors both
        self._fig.savefig(str(path), **kw)
        return path

    def dispose(self) -> None:
        for s in self._surfaces:
            for controller in getattr(s["ax"], "_qtviz_rasters", ()):
                controller.dispose()
            for controller in getattr(s["ax"], "_qtviz_indicators", ()):  # I4b
                controller.dispose()
            brush = getattr(s["ax"], "_qtviz_brush", None)
            if brush is not None:  # detach before the canvas dies ([D95]) — a
                brush.set_active(False)  # live selector on a deleted canvas
                brush.disconnect_events()  # segfaults in queued Qt events
                s["ax"]._qtviz_brush = None
        import contextlib  # noqa: PLC0415

        self.event_bus.dispose()
        # cancel any queued idle draw first so fig.clf()'s stale-callback
        # can't schedule one on a canvas that is mid-destruction
        self._fig.canvas._draw_pending = False
        with contextlib.suppress(RuntimeError):
            self._fig.clf()
        w = self.widget
        if w is not None:
            with contextlib.suppress(RuntimeError):  # C++ half may already be gone
                w.setParent(None)
                w.deleteLater()
        self.widget = None


class MatplotlibBackend:
    name = "matplotlib"
    requires_display = False  # [D125]: renders fine offscreen

    def __init__(self) -> None:
        self.capabilities = _CAPS
        self.renderers = RendererRegistry()
        for element_type, fn in RENDERERS.items():
            self.renderers.register(element_type, fn)

    def supports(self, element_type: type) -> bool:
        # native registration, a [D122] lowering the mark adapter can draw, or
        # a structural element handled in the surface loop (Inset, [D152])
        if self.renderers.get(element_type) is not None:
            return True
        if (issubclass(element_type, Element)
                and getattr(element_type, "STRUCTURAL_CHILD", None)):
            return True
        return (issubclass(element_type, Element)
                and element_type.lower is not Element.lower)

    def honored_options(self, element_type: type) -> frozenset[str]:
        """Recommended options this backend honors (spec §3.4): the native
        table row, else the element's own [D123] lowering declaration."""
        if not issubclass(element_type, Element):
            return frozenset()
        if self.renderers.get(element_type) is not None:
            return element_type.HONORED_NATIVE - HONORED_DELTAS.get(element_type, frozenset())
        if getattr(element_type, "STRUCTURAL_CHILD", None):  # Inset ([D152])
            return element_type.HONORED_NATIVE
        return element_type.HONORED_BY_LOWERING

    def can_host(self, kind: str) -> bool:
        return kind in ("overlay", "grid")

    @require_gui_thread
    def render(self, node, *, theme, parent=None) -> MplRenderHandle:
        node = resolve_node(node)  # accessors → role-keyed eager refs (D14)
        fig = Figure()
        canvas = FigureCanvasQTAgg(fig)
        # A queued draw_idle outliving the canvas is the classic PySide crash
        # (undisposed handles: Qt deletes the widget; a pending _draw_idle —
        # or a figure stale-callback re-arming one — then touches freed C++).
        # `destroyed` fires while the Python wrapper is still valid: shadow the
        # draw methods with no-ops so nothing can render a dead canvas.
        _noop = lambda *a, **k: None  # noqa: E731
        canvas.destroyed.connect(
            lambda *_, c=canvas: c.__dict__.update(
                _draw_pending=False, draw=_noop, draw_idle=_noop, _draw_idle=_noop))
        if parent is not None:
            canvas.setParent(parent)
        apply_theme_fig(fig, theme)
        bus = EventBus()
        surfaces: list = []
        natives: dict = {}
        self._render_into(node, fig, theme, bus, surfaces, natives)
        canvas.draw_idle()
        return MplRenderHandle(canvas, fig, bus, surfaces, node, self, natives)

    # ── internal ──
    # LayoutOptions this backend's single-figure grid honors ([D109]/[D108]):
    # shape (rows/cols incl. mosaic spans), ratios, linking, and the suptitle;
    # spacing/tabs/docks stay host concerns.
    LAYOUT_HONORED = frozenset({"rows", "cols", "link_x", "link_y", "title",
                                "width_ratios", "height_ratios"})

    def _render_into(self, node, fig, theme, bus, surfaces, natives) -> None:
        from collections import deque  # noqa: PLC0415

        from ...core.compose import flat_pane_labels  # noqa: PLC0415

        # [D145]/[D149]: pane identity at render — a deque consumed in
        # traversal order, one per surface and one per inset ([D152]),
        # matching flat_pane_labels' depth-first walk.
        labels = deque(flat_pane_labels(node))
        if isinstance(node, Layout):
            from ...core.compose import grid_geometry  # noqa: PLC0415

            opts = node.options
            check_layout(opts, consumer=self.name, honored=self.LAYOUT_HONORED)
            cells, nrows, ncols = grid_geometry(node)
            gs = fig.add_gridspec(nrows, ncols,
                                  width_ratios=opts.width_ratios,
                                  height_ratios=opts.height_ratios)
            # [D146]: share within link groups — each member shares with its
            # group's first pane (created earlier: the leader is the group min,
            # and children render in index order).
            from ...core.compose import link_groups  # noqa: PLC0415

            n = len(node.children)
            x_leader = {i: g[0] for g in link_groups(cells, n, opts.link_x)
                        for i in g[1:]}
            y_leader = {i: g[0] for g in link_groups(cells, n, opts.link_y)
                        for i in g[1:]}
            leaders: list[int] = []  # surface index of each child's OWN ax:
            for i, (child, (r, c, rs, cs)) in enumerate(
                    zip(node.children, cells, strict=True)):
                ax = fig.add_subplot(
                    gs[r:r + rs, c:c + cs],
                    sharex=(surfaces[leaders[x_leader[i]]]["ax"]
                            if i in x_leader else None),
                    sharey=(surfaces[leaders[y_leader[i]]]["ax"]
                            if i in y_leader else None),
                )
                leaders.append(len(surfaces))  # insets shift surfaces ([D152])
                self._render_cell(child, ax, theme, bus, surfaces, natives, labels)
            if opts.title:
                fig.suptitle(opts.title, color=theme.foreground.mpl(),
                             fontsize=theme.title_size)
        else:
            self._render_cell(node, fig.add_subplot(1, 1, 1), theme, bus, surfaces,
                              natives, labels)

    def _render_cell(self, node, ax, theme, bus, surfaces, natives,
                     labels=None) -> str:
        label = labels.popleft() if labels else "0"
        apply_theme_ax(ax, theme)
        surf = surface_of(node)
        check_surface(surf, consumer=self.name, honored=FULL_SURFACE)  # ([D109])
        x_scale, y_scale = effective_scales(node, surf, self.capabilities.scales, self.name)
        apply_surface(ax, surf, theme, x_scale, y_scale)
        # [D149]: the pane label IS the surface id (RangeEvent source_id) and
        # every emit through the stamping bus carries pane=label.
        bus = PaneBus(bus, label)
        surface_id = label
        selectables: list = []
        children = node.children if isinstance(node, Overlay) else (node,)
        # twin axis ([D88]): created when any series child asks for y2
        ax2, y2_scale = None, "linear"
        if any(getattr(el, "axis", "y") == "y2" for el in children):
            from ...core.compose import resolve_scale  # noqa: PLC0415
            from ...core.options import AxisSpec  # noqa: PLC0415
            from ._surface import apply_y2  # noqa: PLC0415

            y2_spec = surf.y2 if surf.y2 is not None else AxisSpec()
            y2_scale = resolve_scale(y2_spec.scale, self.capabilities.scales,
                                     axis="y2", backend=self.name)
            ax2 = ax.twinx()
            apply_y2(ax2, y2_spec, theme, y2_scale)
        entry = {"ax": ax, "surface_id": surface_id,
                 "selectables": selectables, "y2_ax": ax2, "bus": bus,
                 # pane → element map ([D147]): MplPane.elements reads this.
                 # Insets are chrome here — their contents list on their OWN pane.
                 "element_ids": tuple(
                     el.id for el in children
                     if isinstance(el, Element)
                     and not getattr(el, "STRUCTURAL_CHILD", None))}
        surfaces.append(entry)
        _events.connect_range(ax, surface_id, bus)
        indices = series_index_map(children)  # palette slots; annotations excluded
        ctx = RenderContext(theme=theme, parent=ax, event_bus=bus, backend=self,
                            parent_axes=ax, x_scale=x_scale, y_scale=y_scale,
                            show_legend=surf.legend_enabled,
                            legend_position=surf.legend_position)
        for element, si in zip(children, indices, strict=True):
            if getattr(element, "STRUCTURAL_CHILD", None):  # an Inset ([D152])
                iax = ax.inset_axes(list(element.rect))  # native, mpl semantics
                natives[element.id] = iax  # [D53]: the inset's live Axes
                ilabel = self._render_cell(element.child, iax, theme, bus,
                                           surfaces, natives, labels)
                if element.indicate:  # [D154] + I4b live tracking
                    self._attach_indicator(element, ilabel, iax, ax, ctx, bus,
                                           selectables, natives)
                continue
            on_y2 = getattr(element, "axis", "y") == "y2"
            el_ctx = replace(ctx, series_index=si,
                             parent_axes=ax2 if on_y2 else ax,
                             y_scale=y2_scale if on_y2 else y_scale)
            self._render_element(element, el_ctx, selectables, natives)
        _events.connect_brush(ax, selectables, bus)  # rubber band ([D95])
        # Overlay legend aggregation ([D60]): each child contributes its
        # legend_entry(); merged into any color-mapping legend already drawn.
        if surf.legend_enabled:
            entries = [el.legend_entry(theme, si) for el, si in zip(children, indices, strict=True)
                       if isinstance(el, Element)]
            entries = [e for e in entries if e is not None]
            if entries:
                from ._renderers import append_legend_entries  # noqa: PLC0415

                append_legend_entries(ax, entries, theme, surf.legend_position)
        return label

    def _attach_indicator(self, inset, ilabel, iax, ax, ctx, bus, selectables,
                          natives) -> None:
        """[D154] + I4b — the mpl twin of the pyqtgraph version: draw the
        parent-side rectangle (declared lims, or the inset Axes' rendered
        window) and keep it live via an `InsetIndicator` on the parent Axes."""
        import numpy as np  # noqa: PLC0415

        from ...core._geometry import rect_points  # noqa: PLC0415
        from ...core._indicator import InsetIndicator  # noqa: PLC0415

        window = inset.indicator_window()
        if window is None:  # I4b: mpl lims are data space on every scale
            window = (tuple(iax.get_xlim()), tuple(iax.get_ylim()))
        marker = inset.indicator_rect(window)
        self._render_element(marker, replace(ctx, series_index=0),
                             selectables, natives)
        patch = natives.get(marker.id)
        if patch is None:
            return

        def _move(x0, y0, x1, y1, _patch=patch, _ax=ax) -> None:
            pts = np.asarray(rect_points(x0, y0, x1, y1), dtype="float64")
            _patch.set_xy(pts)
            _ax.figure.canvas.draw_idle()

        controllers = getattr(ax, "_qtviz_indicators", None)
        if controllers is None:
            controllers = ax._qtviz_indicators = []
        controllers.append(InsetIndicator(bus, ilabel, window, _move))

    def _render_element(self, element: Element, ctx, selectables, natives) -> None:
        fn = self.renderers.get(type(element))  # native fast path wins ([D122])
        if fn is None and type(element).lower is not Element.lower:
            from ._marks import render_lowered  # noqa: PLC0415

            fn = render_lowered
        if fn is None:
            raise RendererMissingError(
                f"matplotlib has no renderer for {type(element).__name__}"
            )
        check_recommended(
            element, backend_name=self.name, honored=self.honored_options(type(element))
        )
        artist = fn(element, ctx)
        natives[element.id] = artist
        _events.attach(element, artist, ctx, selectables)
