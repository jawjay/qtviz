"""HoloViewsBackend — converts a HoloViews object into a Bokeh model and
delegates rendering / event wiring / verbs to `BokehBackend`.

This composition (rather than inheritance) keeps the HoloViews surface tiny:
HoloViewsBackend only handles the "HoloViews → Bokeh model" conversion. All
the bridge plumbing — JS injection, event forwarding, patch/stream verbs,
typed events — is inherited as-is from BokehBackend's behavior.

Usage:
    import holoviews as hv
    hv.extension("bokeh")
    from qtwebplot import PlotView
    from qtwebplot.ext.holoviews import HoloViewsBackend

    curve = hv.Curve([(1, 1), (2, 4), (3, 9)])
    view = PlotView(HoloViewsBackend(curve))
    view.show()

    # Events come through the inner Bokeh backend.
    view.backend.events.tap.connect(lambda e: print("tap", e))

    # Replace the figure with another HoloViews object.
    view.set_figure(hv.Bars([("A", 1), ("B", 3), ("C", 2)]))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qtwebplot.backend import PlotBackend
from qtwebplot.ext.bokeh import BokehBackend, BokehEvents

if TYPE_CHECKING:
    from qtwebplot.core import WebBridgeView


class HoloViewsBackend(PlotBackend):
    """Hosts a HoloViews element/layout via the Bokeh renderer."""

    def __init__(
        self,
        hv_object: Any = None,
        *,
        renderer: str = "bokeh",
        resources: str = "cdn",
    ) -> None:
        if renderer != "bokeh":
            raise NotImplementedError(
                "Only the bokeh renderer is supported in v0. "
                "Open an issue if you need the Plotly or Matplotlib renderer."
            )
        self._hv_object = hv_object
        self._renderer_name = renderer
        self._bokeh = BokehBackend(resources=resources)
        if hv_object is not None:
            self._bokeh.set_figure(self._to_bokeh(hv_object))

    # ── PlotBackend protocol (delegate) ──────────────────────────────────
    def to_html(self) -> str:
        return self._bokeh.to_html()

    def js_runtime(self) -> str | None:
        return self._bokeh.js_runtime()

    def on_attach(self, view: WebBridgeView) -> None:
        self._bokeh.on_attach(view)

    def on_detach(self) -> None:
        self._bokeh.on_detach()

    def set_figure(self, figure: Any) -> None:
        self._hv_object = figure
        self._bokeh.set_figure(self._to_bokeh(figure))

    def apply_theme(self, theme) -> None:
        # Delegate — the inner Bokeh model gets the theme on render.
        self._bokeh.apply_theme(theme)

    # ── HoloViews-specific accessors ─────────────────────────────────────
    @property
    def hv_object(self) -> Any:
        """The current HoloViews element/layout, untouched."""
        return self._hv_object

    @property
    def bokeh(self) -> BokehBackend:
        """The inner BokehBackend — reach in for Bokeh verbs (patch/stream/...)
        and the underlying Bokeh model (`backend.bokeh.figure`)."""
        return self._bokeh

    @property
    def events(self) -> BokehEvents:
        """Same as `backend.bokeh.events`, lifted for convenience.
        Event payloads describe the Bokeh model that HoloViews built — not
        the HoloViews abstraction. Tap/selection refer to the underlying
        Bokeh glyph; map back to HoloViews state in your handler.
        """
        return self._bokeh.events

    # ── internals ────────────────────────────────────────────────────────
    def _to_bokeh(self, hv_object: Any) -> Any:
        import holoviews as hv  # noqa: PLC0415

        hv.extension(self._renderer_name)
        renderer = hv.renderer(self._renderer_name)
        # `get_plot(obj).state` is the Bokeh model (Figure, GridPlot, ...).
        return renderer.get_plot(hv_object).state
