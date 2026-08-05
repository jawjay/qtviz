"""webengine backend — render + RenderHandle (roadmap Phase 5, W1).

Wraps the legacy Qt↔JS bridge behind the qtviz `Backend` protocol: Elements
become a Plotly figure (`_figure`), hosted in a `WebBridgeView` via the legacy
`PlotlyBackend`; the bridge's `received` messages are translated to qtviz typed
events (`_translate`). Render returns immediately and the bridge's command queue
buffers anything sent before the page is `ready` (D25) — so the synchronous
`Backend.render` contract holds over an async page load.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

from ...core._scales import delog, log_lim
from ...core.backend import PaneHandle, RendererRegistry, RenderHandle, ViewState
from ...core.capabilities import Capabilities
from ...core.event import EventBus, RangeEvent
from ...core.threading import require_gui_thread
from ...elements import RawFigure
from . import _figure, _translate
from .ext.plotly.backend import PlotlyBackend

# NB: `.view` (PlotView) pulls in PySide6 QtWebEngine — imported lazily inside
# render()/_render_raw so registering this backend at `import qtviz` stays
# WebEngine-free (de-flake; the default suite never loads Chromium).
if TYPE_CHECKING:
    from .view import PlotView

_CAPS = Capabilities(
    dimensions=frozenset({2}),   # honest: no 3-D renderer exists ([D52]); was aspirational {2,3}
    opengl=True,                 # Plotly scattergl
    picking="native",
    brush="native",              # box / lasso select
    range_events=True,
    streaming=True,
    max_recommended_points=1_000_000,
    animation=False,  # honest: no animation API ([D52], §12 out of scope)
    # png via QWebEngineView.grab (a rendered page); svg/pdf would need kaleido — later.
    exports=frozenset({"png"}),
    threading_model="gui_only",
    # Plotly renders log natively (`xaxis.type="log"`); its relayout/range values
    # are log10, normalized at the handle boundary (R1). symlog is Plotly-less.
    scales=frozenset({"linear", "log"}),
)


class _WebPane(PaneHandle):
    """The one surface of a webengine figure ([D147]). Ranges come from the
    handle's shadow state — Python-held, data space — so `capture` is
    synchronous even though the live ranges live in JS; restores go out over
    the bridge (queued until it is ready), log axes normalized on the wire
    (R1)."""

    def __init__(self, label: str, handle: WebEngineRenderHandle) -> None:
        super().__init__(label)
        self._h = handle

    def capture(self) -> ViewState:
        return ViewState(x_range=self._h._x_range, y_range=self._h._y_range)

    @require_gui_thread
    def restore(self, state: ViewState) -> None:
        self._assert_alive()
        h = self._h
        update: dict = {}
        if state.x_range:
            h._x_range = state.x_range              # shadow state stays data space
            sent = log_lim(state.x_range, axis="x", backend="webengine") \
                if h._x_log else state.x_range      # …the wire wants log10 (R1)
            if sent:
                update["xaxis.range"] = list(sent)
        if state.y_range:
            h._y_range = state.y_range
            sent = log_lim(state.y_range, axis="y", backend="webengine") \
                if h._y_log else state.y_range
            if sent:
                update["yaxis.range"] = list(sent)
        if update:
            h._host.relayout(update)  # queued until the bridge is ready

    @require_gui_thread
    def autorange(self) -> None:
        self._assert_alive()
        self._h._x_range = None  # unknown until the relayout reports back
        self._h._y_range = None
        self._h._host.relayout({"xaxis.autorange": True, "yaxis.autorange": True})

    @property
    def native(self):
        return self._h._host

    @property
    def elements(self) -> tuple[str, ...]:
        return tuple(self._h._traces)

    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        self._assert_alive()  # one figure = one pane: the handle export IS it
        return self._h.export(fmt, path, dpi=dpi, transparent=transparent)


class WebEngineRenderHandle(RenderHandle):
    """Owns the `WebBridgeView`, the Plotly host, and the event bridge. Tracks
    last-known axis ranges (shadow state) so state capture is synchronous even
    though the live ranges live in JS."""

    def __init__(self, widget: PlotView, event_bus, host, source_ids, surface_id, theme,
                 fig: dict | None = None) -> None:
        super().__init__(widget, event_bus, "webengine")
        self._host = host
        self._traces = list(source_ids)
        self._surface_id = surface_id
        self._theme = theme
        self._x_range: tuple[float, float] | None = None  # shadow state, DATA space (R1)
        self._y_range: tuple[float, float] | None = None
        self._rasters: list = []  # dynamic-raster controllers (4b, `_raster`)
        self._raster_holders: dict = {}  # element id → live RasterAggregate ([D46] hover)
        self._set_log_flags(fig)
        widget.received.connect(self._on_message)

    def _set_log_flags(self, fig: dict | None) -> None:
        """Whether each axis is log — read off the built figure spec (its layout is
        the source of truth). Plotly's relayout/range values are log10 on a log axis,
        so these flags drive the R1 normalization below. RawFigure hosts (no qtviz
        figure spec) keep both False — their ranges pass through untouched."""
        layout = (fig or {}).get("layout", {})
        self._x_log = layout.get("xaxis", {}).get("type") == "log"
        self._y_log = layout.get("yaxis", {}).get("type") == "log"

    def _on_message(self, name: str, payload) -> None:
        if name == "plotly.relayout":
            update = payload.get("update", {}) if isinstance(payload, dict) else {}
            self._merge_range(*_translate.parse_relayout(update))
            return
        if name == "bokeh.ranges_update":
            self._merge_range(*_translate.parse_bokeh_ranges(payload))
            return
        events = _translate.translate(
            name, payload, traces=self._traces, surface_id=self._surface_id
        )
        from dataclasses import replace  # noqa: PLC0415

        for ev in events:
            ev = self._with_raster_value(ev)
            if ev.pane is None:  # [D149]: one figure = one pane
                ev = replace(ev, pane=self._surface_id)
            self.event_bus.emit(ev)

    def _with_raster_value(self, ev):
        """[D46]: a hover over a datashaded raster carries the aggregated value
        under the cursor — looked up in the live `RasterAggregate` (refreshed by
        the controller on every re-aggregation), matching pyqtgraph/matplotlib."""
        from ...core.event import HoverEvent  # noqa: PLC0415

        holder = self._raster_holders.get(getattr(ev, "source_id", None))
        if holder is None or not isinstance(ev, HoverEvent) or ev.value is not None:
            return ev
        agg = getattr(holder, "aggregate", None)
        if agg is None:
            return ev
        import dataclasses  # noqa: PLC0415

        return dataclasses.replace(ev, value=agg.value_at(ev.x, ev.y))

    def _merge_range(self, x, y) -> None:
        """Merge a (possibly partial) range update into the shadow state and emit
        a RangeEvent once both axes are known (Plotly relayout / Bokeh ranges).
        Incoming log-axis values are log10 — normalized to data space here (R1),
        so the shadow state, `capture_state`, and every RangeEvent are data space."""
        if x is None and y is None:
            return
        if x is not None:
            self._x_range = (delog(x[0], self._x_log), delog(x[1], self._x_log))
        if y is not None:
            self._y_range = (delog(y[0], self._y_log), delog(y[1], self._y_log))
        if self._x_range is not None and self._y_range is not None:
            self.event_bus.emit(RangeEvent(self._surface_id, self._x_range,
                                           self._y_range, pane=self._surface_id))

    def native(self, element_id: str):
        """The live Plotly host (verbs: react/relayout/…) for any element this
        figure drew — webengine has no per-element primitive (it's one JS figure),
        so the host is the reachable native object ([D53])."""
        return self._host if element_id in self._traces else None

    def _panes(self) -> tuple[PaneHandle, ...]:
        # one figure = one surface; grids compose per-pane handles via the host
        return (_WebPane("0", self),)

    @require_gui_thread
    def update(self, new_root) -> None:
        from . import _raster  # noqa: PLC0415

        _raster.dispose_rasters(self)  # trace indices are about to change
        fig, source_ids = _figure.build(new_root, self._theme)
        self._traces = source_ids
        self._set_log_flags(fig)  # the new root may change axis scales
        self._host.react(fig)
        self._wire_rasters(new_root)

    def _wire_rasters(self, node) -> None:
        """Attach the dynamic re-aggregation loop (4b) for datashaded elements.
        Log axes are skipped: `plotly.view` ranges arrive log10 and a raster on
        a log axis is unsupported on every backend."""
        if self._x_log or self._y_log:
            return
        from . import _raster  # noqa: PLC0415

        _raster.wire_dynamic_rasters(self, node, self._theme)

    def export(self, fmt: str, path, *, dpi: float | None = None,
               transparent: bool = False) -> Path:
        if dpi is not None or transparent:  # honor-or-warn ([D72])
            import warnings  # noqa: PLC0415

            from ...errors import QtvizWarning  # noqa: PLC0415

            warnings.warn("webengine: export knobs (dpi/transparent) are not honored "
                          "(the page is grabbed as rendered) and were ignored.",
                          QtvizWarning, stacklevel=2)
        if fmt != "png":
            raise NotImplementedError(
                f"webengine exports png (svg/pdf would need kaleido); got {fmt!r}"
            )
        if self.widget.size().isEmpty():
            self.widget.resize(800, 600)  # grab needs a non-empty widget
        return self.widget.to_png(path)

    def dispose(self) -> None:
        from . import _raster  # noqa: PLC0415

        _raster.dispose_rasters(self)
        w = self.widget
        if w is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                w.received.disconnect(self._on_message)
        self._host.on_detach()
        super().dispose()


class WebEngineBackend:
    name = "webengine"
    requires_display = True  # the live render path needs a real GPU/compositor

    def __init__(self) -> None:
        self.capabilities = _CAPS
        self.renderers = RendererRegistry()
        for element_type in _figure.supported_types():
            self.renderers.register(element_type, _figure._TRACE_BUILDERS[element_type])

    def supports(self, element_type: type) -> bool:
        # RawFigure is a passthrough (D26); everything else is a native trace
        # builder or a [D122] lowering the mark adapter can draw.
        if element_type is RawFigure or self.renderers.get(element_type) is not None:
            return True
        from ...core.element import Element  # noqa: PLC0415

        if (issubclass(element_type, Element)
                and getattr(element_type, "STRUCTURAL_CHILD", None)):
            # Inset ([D152]): accepted so negotiation proceeds; the figure
            # builder warns-and-skips it until I5 (design/inset-axes.md).
            return True
        return (issubclass(element_type, Element)
                and element_type.lower is not Element.lower)

    def honored_options(self, element_type: type) -> frozenset[str]:
        """Recommended options this backend honors (spec §3.4): the native
        table row, else the element's own [D123] lowering declaration."""
        return _figure.honored_for(element_type)

    def can_host(self, kind: str) -> bool:
        # No native mixed panes — the LayoutHost composes per-pane WebBridgeViews.
        return False

    @require_gui_thread
    def render(self, node, *, theme, parent=None) -> WebEngineRenderHandle:
        from .view import PlotView  # noqa: PLC0415 — lazy: defers the QtWebEngine load

        if isinstance(node, RawFigure):
            return self._render_raw(node, parent, theme)
        # native-element path: build one Plotly figure from the traces. A RawFigure
        # nested in an Overlay is rejected here by `_figure.build` (it's standalone).
        fig, source_ids = _figure.build(node, theme)
        host = PlotlyBackend(fig)
        view = PlotView(host, parent=parent)
        bus = EventBus()
        handle = WebEngineRenderHandle(view, bus, host, source_ids, "0", theme,
                                       fig=fig)
        handle._wire_rasters(node)
        return handle

    def _render_raw(self, node: RawFigure, parent, theme) -> WebEngineRenderHandle:
        """Host an existing Plotly/Bokeh/HoloViews figure unchanged (D31). The
        whole figure is one event source (its own id). Bokeh/HoloViews figures
        render in W3a but emit typed events only once W3b adds the Bokeh map."""
        from .view import PlotView  # noqa: PLC0415 — lazy: defers the QtWebEngine load

        host = _make_host(node.kind, node.figure)
        view = PlotView(host, parent=parent)
        bus = EventBus()
        return WebEngineRenderHandle(view, bus, host, [node.id], "0", theme)


def _make_host(kind: str, figure):
    """The legacy PlotBackend host for a raw figure of the given library."""
    if kind == "plotly":
        return PlotlyBackend(figure)
    if kind == "bokeh":
        from .ext.bokeh.backend import BokehBackend  # noqa: PLC0415

        return BokehBackend(figure)
    if kind == "holoviews":
        from .ext.holoviews.backend import HoloViewsBackend  # noqa: PLC0415

        return HoloViewsBackend(figure)
    from ...errors import ValidationError  # noqa: PLC0415

    raise ValidationError(f"unknown RawFigure kind {kind!r}")


backend = WebEngineBackend()
