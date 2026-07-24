"""pyqtgraph backend — render + RenderHandle (spec §4.1)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pyqtgraph as pg

from ...core._degrade import check_recommended
from ...core._scales import delog, log_lim
from ...core.backend import RenderContext, RendererRegistry, RenderHandle, ViewState
from ...core.capabilities import Capabilities
from ...core.compose import Layout, Overlay, effective_scales, surface_of
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
    scales=frozenset({"linear", "log"}),
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
        return ViewState(
            x_range=(delog(x0, x_log), delog(x1, x_log)),
            y_range=(delog(y0, y_log), delog(y1, y_log)),
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

    def export(self, fmt: str, path) -> Path:
        from pyqtgraph.exporters import ImageExporter, SVGExporter  # noqa: PLC0415

        path = Path(path)
        scene = self._plots[0].scene()
        exporter = SVGExporter(scene) if fmt == "svg" else ImageExporter(scene)
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
    def _render_into(self, node, widget, theme, bus, plots, natives) -> None:
        if isinstance(node, Layout):
            ncols = node.options.cols or len(node.children)
            for i, child in enumerate(node.children):
                r, c = divmod(i, ncols)
                self._render_cell(child, widget, theme, bus, plots, natives, r, c)
            opts = node.options
            if opts.link_x or opts.link_y:
                link_axes(plots, link_x=opts.link_x, link_y=opts.link_y)
        else:
            self._render_cell(node, widget, theme, bus, plots, natives, 0, 0)

    def _render_cell(self, node, widget, theme, bus, plots, natives, row, col) -> None:
        surf = surface_of(node)
        x_scale, y_scale = effective_scales(node, surf, self.capabilities.scales, self.name)
        vb = QtvizViewBox(bus=bus, surface_id=uuid.uuid4().hex,
                          x_log=(x_scale == "log"), y_log=(y_scale == "log"))
        plot = widget.addPlot(row=row, col=col, viewBox=vb)
        style_plot(plot, theme)
        apply_surface(plot, surf, theme, x_scale, y_scale)
        plots.append(plot)
        children = node.children if isinstance(node, Overlay) else (node,)
        ctx = RenderContext(theme=theme, parent=plot, event_bus=bus, backend=self,
                            parent_axes=plot, x_scale=x_scale, y_scale=y_scale,
                            show_legend=surf.legend_enabled,
                            legend_position=surf.legend_position)
        for element in children:
            self._render_element(element, ctx, natives)
        # Overlay legend aggregation ([D60]): each child contributes its
        # legend_entry(); merged into any color-mapping legend already drawn.
        if surf.legend_enabled:
            entries = [el.legend_entry(theme, i) for i, el in enumerate(children)
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
