"""pyqtgraph backend — render + RenderHandle (spec §4.1)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path

import pyqtgraph as pg

from ...core._degrade import FULL_SURFACE, check_layout, check_recommended, check_surface
from ...core._scales import delog, log_lim, logify
from ...core.backend import RenderContext, RendererRegistry, RenderHandle, ViewState
from ...core.capabilities import Capabilities
from ...core.compose import (
    Layout,
    Overlay,
    effective_scales,
    series_index_map,
    surface_of,
)
from ...core.element import Element
from ...core.event import EventBus
from ...core.threading import require_gui_thread
from ...data import resolve_node
from ...errors import RendererMissingError
from . import _events
from ._axes import link_axes
from ._interaction import QtvizViewBox
from ._renderers import HONORED, RENDERERS
from ._surface import apply_surface
from ._theme import apply_theme, style_plot

_CAPS = Capabilities(
    dimensions=frozenset({2}),
    opengl=True,
    picking="native",
    brush="native",
    range_events=True,
    streaming=True,
    max_recommended_points=2_000_000,
    animation=False,
    # png only for now: pyqtgraph's SVGExporter is fragile, and vector export
    # (svg/pdf) is the matplotlib backend's role by design (roadmap Phase 2).
    exports=frozenset({"png"}),
    threading_model="gui_only",
    # log via Approach A (pre-log10'd data + log-tick AxisItem + R1 at the event
    # boundaries); symlog is matplotlib-only (pyqtgraph #1035) and warn-degrades.
    scales=frozenset({"linear", "log", "time"}),  # time: [D94]
)


class PgRenderHandle(RenderHandle):
    def __init__(self, widget, event_bus, plots, root, backend, natives) -> None:
        super().__init__(widget, event_bus, "pyqtgraph")
        self._plots = plots
        self._root = root
        self._backend = backend
        self._natives = natives  # element id → ScatterPlotItem / PlotCurveItem / … ([D53])

    @property
    def plots(self):
        return self._plots

    def _vb(self):
        return self._plots[0].getViewBox() if self._plots else None

    def capture_state(self) -> ViewState:
        """Portable state is **data space** (R1): under log the ViewBox range is in
        exponent space and is de-logged here, so a `ViewState` round-trips across
        rebuilds and backend switches unchanged."""
        vb = self._vb()
        if vb is None:
            return ViewState()
        (x0, x1), (y0, y1) = vb.viewRange()
        x_log, y_log = getattr(vb, "x_log", False), getattr(vb, "y_log", False)
        y2_range = None
        vb2 = getattr(self._plots[0], "_qtviz_vb2", None)
        if vb2 is not None:  # twin axis ([D88])
            (_, _), (b0, b1) = vb2.viewRange()
            y2_log = getattr(vb2, "y_log", False)
            y2_range = (delog(b0, y2_log), delog(b1, y2_log))
        return ViewState(
            x_range=(delog(x0, x_log), delog(x1, x_log)),
            y_range=(delog(y0, y_log), delog(y1, y_log)),
            y2_range=y2_range,
        )

    def restore_state(self, state: ViewState) -> None:
        vb = self._vb()
        if vb is None:
            return
        x_rng, y_rng = state.x_range, state.y_range
        if x_rng and getattr(vb, "x_log", False):
            x_rng = log_lim(x_rng, axis="x", backend="pyqtgraph")
        if y_rng and getattr(vb, "y_log", False):
            y_rng = log_lim(y_rng, axis="y", backend="pyqtgraph")
        if x_rng:
            vb.setXRange(*x_rng, padding=0)
        if y_rng:
            vb.setYRange(*y_rng, padding=0)
        vb2 = getattr(self._plots[0], "_qtviz_vb2", None) if self._plots else None
        if vb2 is not None and state.y2_range is not None:
            y2_rng = (log_lim(state.y2_range, axis="y2", backend="pyqtgraph")
                      if getattr(vb2, "y_log", False) else state.y2_range)
            if y2_rng:
                vb2.setYRange(*y2_rng, padding=0)

    def _dispose_rasters(self) -> None:
        for plot in self._plots:
            vb = plot.getViewBox()
            for controller in getattr(vb, "_qtviz_rasters", ()):
                controller.dispose()
            if hasattr(vb, "_qtviz_rasters"):
                vb._qtviz_rasters = []

    def dispose(self) -> None:
        self._dispose_rasters()
        super().dispose()

    @require_gui_thread
    def set_element_data(self, element_id: str, arrays: dict) -> bool:
        """In-place refresh ([D77]): `setData` on the live Scatter/Curve item —
        milliseconds at 100k points, no rebuild. Positions logify under a log
        surface (R1) and the ViewBox selectable registry is refreshed so
        brushing stays truthful. Per-point styling roles (color/size) and other
        item types return False → the caller falls back."""
        import numpy as np  # noqa: PLC0415

        # streaming × datashader (retrospective §4.2): the element's live ref
        # already holds the new rows — re-aggregating the current viewport IS
        # the in-place update, through the controller's debounce/off-thread/
        # stale-drop machinery. No rebuild.
        for plot in self._plots:
            for controller in getattr(plot.getViewBox(), "_qtviz_rasters", ()):
                if getattr(controller, "element_id", None) == element_id:
                    controller.refresh()
                    return True
        item = self._natives.get(element_id)
        if not isinstance(item, (pg.ScatterPlotItem, pg.PlotCurveItem, pg.PlotDataItem)):
            return False
        if getattr(item, "opts", {}).get("stepMode") == "center":
            return False  # center-step wants n+1 edges — fall back to a re-render
        if set(arrays) != {"x", "y"}:  # styling channels need a real re-render
            return False
        x = np.asarray(arrays["x"], dtype="float64")
        y = np.asarray(arrays["y"], dtype="float64")
        vb = item.getViewBox()
        x_log = getattr(vb, "x_log", False)
        y_log = getattr(vb, "y_log", False)
        item.setData(x=logify(x, x_log), y=logify(y, y_log))
        selectables = getattr(vb, "_selectables", None)
        if selectables is not None:  # brush masks run in data space
            for i, entry in enumerate(selectables):
                if entry[0] == element_id:
                    selectables[i] = (element_id, x, y)
        return True

    @require_gui_thread
    def update(self, new_root) -> None:
        self._dispose_rasters()
        for plot in self._plots:
            plot.clear()
        self._plots.clear()
        self._natives.clear()  # rebuilt below so native() reflects the new render
        self._backend._render_into(
            new_root, self.widget, self._theme_ref(), self.event_bus, self._plots, self._natives
        )
        self._root = new_root

    def _theme_ref(self):
        return self._backend._last_theme

    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        from pyqtgraph.exporters import ImageExporter, SVGExporter  # noqa: PLC0415

        if dpi is not None:  # honor-or-warn ([D72]): pyqtgraph exports at pixel size
            import warnings  # noqa: PLC0415

            from ...errors import QtvizWarning  # noqa: PLC0415

            warnings.warn("pyqtgraph: 'dpi' is not honored (raster exports at widget "
                          "pixel size) and was ignored.", QtvizWarning, stacklevel=2)
        path = Path(path)
        scene = self._plots[0].scene()
        exporter = SVGExporter(scene) if fmt == "svg" else ImageExporter(scene)
        if transparent and fmt != "svg":
            from PySide6.QtGui import QColor  # noqa: PLC0415

            exporter.parameters()["background"] = QColor(0, 0, 0, 0)
        exporter.export(str(path))
        return path


class PyQtGraphBackend:
    name = "pyqtgraph"

    def __init__(self) -> None:
        self.capabilities = _CAPS
        self.renderers = RendererRegistry()
        for element_type, fn in RENDERERS.items():
            self.renderers.register(element_type, fn)
        self._last_theme = None

    def supports(self, element_type: type) -> bool:
        return self.renderers.get(element_type) is not None

    def honored_options(self, element_type: type) -> frozenset[str]:
        """Recommended options this backend honors for `element_type` (spec §3.4)."""
        return HONORED.get(element_type, frozenset())

    def can_host(self, kind: str) -> bool:
        return kind in ("overlay", "grid")

    @require_gui_thread
    def render(self, node, *, theme, parent=None) -> PgRenderHandle:
        node = resolve_node(node)  # accessors → role-keyed eager refs (D14)
        self._last_theme = theme
        widget = pg.GraphicsLayoutWidget(parent=parent)
        apply_theme(widget, theme)
        bus = EventBus()
        plots: list = []
        natives: dict = {}
        self._render_into(node, widget, theme, bus, plots, natives)
        return PgRenderHandle(widget, bus, plots, node, self, natives)

    # ── internal ──
    LAYOUT_HONORED = frozenset({"cols", "link_x", "link_y"})  # ([D109])

    def _render_into(self, node, widget, theme, bus, plots, natives) -> None:
        if isinstance(node, Layout):
            check_layout(node.options, consumer=self.name, honored=self.LAYOUT_HONORED)
            ncols = node.options.cols or len(node.children)
            for i, child in enumerate(node.children):
                r, c = divmod(i, ncols)
                self._render_cell(child, widget, theme, bus, plots, natives, r, c)
            opts = node.options
            if opts.link_x or opts.link_y:
                link_axes(plots, link_x=opts.link_x, link_y=opts.link_y)
        else:
            self._render_cell(node, widget, theme, bus, plots, natives, 0, 0)

    # [D109]: everything except tick label rotation (no stable AxisItem API).
    SURFACE_HONORED = FULL_SURFACE - {"x.tick_rotation", "y.tick_rotation"}

    def _render_cell(self, node, widget, theme, bus, plots, natives, row, col) -> None:
        surf = surface_of(node)
        check_surface(surf, consumer=self.name, honored=self.SURFACE_HONORED)
        x_scale, y_scale = effective_scales(node, surf, self.capabilities.scales, self.name)
        vb = QtvizViewBox(bus=bus, surface_id=uuid.uuid4().hex,
                          x_log=(x_scale == "log"), y_log=(y_scale == "log"))
        plot = widget.addPlot(row=row, col=col, viewBox=vb)
        style_plot(plot, theme)
        apply_surface(plot, surf, theme, x_scale, y_scale)
        plots.append(plot)
        children = node.children if isinstance(node, Overlay) else (node,)
        # twin axis ([D88]): created when any series child asks for y2
        y2_host, y2_scale = None, "linear"
        if any(getattr(el, "axis", "y") == "y2" for el in children):
            from ...core.compose import resolve_scale  # noqa: PLC0415
            from ...core.options import AxisSpec  # noqa: PLC0415
            from ._surface import _Y2Host, make_y2  # noqa: PLC0415

            y2_spec = surf.y2 if surf.y2 is not None else AxisSpec()
            y2_scale = resolve_scale(y2_spec.scale, self.capabilities.scales,
                                     axis="y2", backend=self.name)
            vb2 = make_y2(plot, vb, y2_spec, theme, x_scale, y2_scale)
            plot._qtviz_vb2 = vb2
            y2_host = _Y2Host(plot, vb2)
        indices = series_index_map(children)  # palette slots; annotations excluded
        ctx = RenderContext(theme=theme, parent=plot, event_bus=bus, backend=self,
                            parent_axes=plot, x_scale=x_scale, y_scale=y_scale,
                            show_legend=surf.legend_enabled,
                            legend_position=surf.legend_position)
        for element, si in zip(children, indices, strict=True):
            on_y2 = getattr(element, "axis", "y") == "y2"
            el_ctx = replace(ctx, series_index=si,
                             parent_axes=y2_host if on_y2 else plot,
                             y_scale=y2_scale if on_y2 else y_scale)
            self._render_element(element, el_ctx, natives)
        # Overlay legend aggregation ([D60]): each child contributes its
        # legend_entry(); merged into any color-mapping legend already drawn.
        if surf.legend_enabled:
            entries = [el.legend_entry(theme, si) for el, si in zip(children, indices, strict=True)
                       if isinstance(el, Element)]
            entries = [e for e in entries if e is not None]
            if entries:
                from ._legend import append_legend_entries  # noqa: PLC0415

                append_legend_entries(plot, entries, theme, surf.legend_position)

    def _render_element(self, element: Element, ctx, natives) -> None:
        fn = self.renderers.get(type(element))
        if fn is None:
            raise RendererMissingError(
                f"pyqtgraph has no renderer for {type(element).__name__}"
            )
        check_recommended(
            element, backend_name=self.name, honored=self.honored_options(type(element))
        )
        item = fn(element, ctx)
        natives[element.id] = item
        _events.attach(element, item, ctx)
