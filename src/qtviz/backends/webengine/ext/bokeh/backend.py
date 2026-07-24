"""BokehBackend — hosts a Bokeh figure in a `PlotView` / `WebBridgeView`.

The implementation strategy differs from `PlotlyBackend` in two notable ways,
which is precisely the point of having a second backend — it proves the core
abstractions don't force a single library's idioms on every extension:

1. **Event forwarding is Python-side, not JS-side.** Bokeh's idiomatic way to
   handle events in a static embed is `figure.js_on_event(EventType,
   CustomJS(code=...))`. We mutate the figure on first render to install
   CustomJS callbacks that call `qtwebplot.send(...)`. (Plotly uses runtime
   `div.on(eventName, ...)` JS, which is wired in `_runtime.py`.)
2. **Verbs target models by name, not a fixed div.** Bokeh figures are made
   of named models (ColumnDataSource, glyph renderers, axes); we look them
   up via `Bokeh.documents[0].select({name: ...})`. Callers tag their models
   with `name="..."` to make them addressable.

Usage:
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource
    from qtviz.backends.webengine import PlotView
    from qtviz.backends.webengine.ext.bokeh import BokehBackend

    src = ColumnDataSource(data={"x": [1,2,3], "y": [1,4,9]}, name="src")
    p = figure(height=400)
    p.line("x", "y", source=src)

    backend = BokehBackend(p)
    view = PlotView(backend)
    view.show()

    backend.patch("src", {"x": [1,2,3,4,5], "y": [1,4,9,16,25]})
    backend.events.tap.connect(lambda e: print("tap @", e.x, e.y))
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from qtviz.backends.webengine.backend import PlotBackend
from qtviz.backends.webengine.ext.bokeh._runtime import BOKEH_JS
from qtviz.backends.webengine.ext.bokeh.events import (
    BokehDoubleTapEvent,
    BokehEvents,
    BokehRangesUpdateEvent,
    BokehSelectionEvent,
    BokehTapEvent,
)

if TYPE_CHECKING:
    from qtviz.backends.webengine.core import WebBridgeView
    from qtviz.backends.webengine.theme import Theme


_INSTRUMENTED_MARKER = "_qtwebplot_instrumented"


class BokehBackend(PlotBackend):
    """Hosts a Bokeh figure in a `PlotView` (or any `WebBridgeView`)."""

    def __init__(self, figure: Any = None, *, resources: str = "inline") -> None:
        # resources="inline" embeds BokehJS from the installed package → no network
        # (spec §0.1 offline requirement). Pass "cdn" to opt back in.
        self._figure = figure
        self._resources = resources
        self._view: WebBridgeView | None = None
        self._events = BokehEvents()
        self._bk_theme: Any = None  # bokeh.themes.Theme, lazy-built

    # ── PlotBackend protocol ─────────────────────────────────────────────
    def to_html(self) -> str:
        from bokeh.embed import file_html
        from bokeh.resources import CDN, INLINE

        if self._figure is None:
            return "<html><body></body></html>"

        self._instrument(self._figure)
        res = INLINE if self._resources == "inline" else CDN
        kwargs: dict = {"title": "qtwebplot"}
        if self._bk_theme is not None:
            kwargs["theme"] = self._bk_theme
        return file_html(self._figure, res, **kwargs)

    def js_runtime(self) -> str:
        return BOKEH_JS

    def on_attach(self, view: WebBridgeView) -> None:
        self._view = view
        view.received.connect(self._on_message)

    def on_detach(self) -> None:
        if self._view is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self._view.received.disconnect(self._on_message)
        self._view = None

    def set_figure(self, figure: Any) -> None:
        self._figure = figure

    def apply_theme(self, theme: Theme) -> None:
        """Convert the qtwebplot Theme to a `bokeh.themes.Theme` and store it.
        Applied during `to_html()` via `file_html(theme=...)`.
        """
        from bokeh.themes import Theme as BkTheme

        attrs = {
            "figure": {
                "background_fill_color": theme.background,
                "border_fill_color": theme.background,
                "outline_line_color": theme.grid,
            },
            "Axis": {
                "axis_label_text_color": theme.foreground,
                "major_label_text_color": theme.foreground,
                "axis_line_color": theme.foreground,
                "major_tick_line_color": theme.foreground,
                "minor_tick_line_color": theme.grid,
            },
            "Grid": {
                "grid_line_color": theme.grid,
            },
            "Title": {
                "text_color": theme.foreground,
                "text_font": theme.font_family,
            },
            "Legend": {
                "background_fill_color": theme.background,
                "label_text_color": theme.foreground,
                "border_line_color": theme.grid,
            },
        }
        self._bk_theme = BkTheme(json={"attrs": attrs})

    # ── Bokeh verbs (use the generic bridge transport) ───────────────────
    @property
    def events(self) -> BokehEvents:
        return self._events

    @property
    def figure(self) -> Any:
        return self._figure

    def patch(self, source_name: str, data: dict) -> None:
        """Replace a named ColumnDataSource's data wholesale."""
        self._require_view().send("bokeh.patch", {"name": source_name, "data": data})

    def stream(
        self,
        source_name: str,
        data: dict,
        max_points: int | None = None,
    ) -> None:
        """Append rows to a named ColumnDataSource."""
        self._require_view().send(
            "bokeh.stream",
            {"name": source_name, "data": data, "max_points": max_points},
        )

    def set_property(self, model_name: str, property: str, value: Any) -> None:
        """Set an arbitrary property on a named Bokeh model."""
        self._require_view().send(
            "bokeh.set_property",
            {"name": model_name, "property": property, "value": value},
        )

    # ── internals ────────────────────────────────────────────────────────
    def _require_view(self) -> WebBridgeView:
        if self._view is None:
            raise RuntimeError(
                "BokehBackend is not attached to a view. "
                "Did you forget to pass it to PlotView()?"
            )
        return self._view

    def _instrument(self, figure: Any) -> None:
        """Inject CustomJS callbacks that forward Bokeh events to the bridge.

        Idempotent — tagged via an attribute so repeated `to_html` calls don't
        stack duplicate callbacks. (We can't tag a Bokeh model via setattr in
        all versions, so we store in a side dict.)
        """
        if id(figure) in _INSTRUMENTED_IDS:
            return

        from bokeh.events import (
            DoubleTap,
            RangesUpdate,
            SelectionGeometry,
            Tap,
        )
        from bokeh.models import CustomJS

        tap_cb = CustomJS(
            code=(
                "if (window.qtwebplot) "
                "qtwebplot.send('bokeh.tap', "
                "{x: cb_obj.x, y: cb_obj.y, sx: cb_obj.sx, sy: cb_obj.sy});"
            )
        )
        dtap_cb = CustomJS(
            code=(
                "if (window.qtwebplot) "
                "qtwebplot.send('bokeh.double_tap', "
                "{x: cb_obj.x, y: cb_obj.y, sx: cb_obj.sx, sy: cb_obj.sy});"
            )
        )
        sel_cb = CustomJS(
            code=(
                "if (window.qtwebplot) "
                "qtwebplot.send('bokeh.selection', "
                "{geometry: cb_obj.geometry});"
            )
        )
        range_cb = CustomJS(
            code=(
                "if (window.qtwebplot) "
                "qtwebplot.send('bokeh.ranges_update', "
                "{x0: cb_obj.x0, x1: cb_obj.x1, y0: cb_obj.y0, y1: cb_obj.y1});"
            )
        )

        figure.js_on_event(Tap, tap_cb)
        figure.js_on_event(DoubleTap, dtap_cb)
        figure.js_on_event(SelectionGeometry, sel_cb)
        figure.js_on_event(RangesUpdate, range_cb)
        _INSTRUMENTED_IDS.add(id(figure))

    def _on_message(self, name: str, payload: object) -> None:
        if not name.startswith("bokeh."):
            return
        if not isinstance(payload, dict):
            return
        kind = name.split(".", 1)[1]
        if kind == "tap":
            self._events.tap.emit(
                BokehTapEvent(
                    x=payload.get("x"),
                    y=payload.get("y"),
                    sx=payload.get("sx"),
                    sy=payload.get("sy"),
                    raw=payload,
                )
            )
        elif kind == "double_tap":
            self._events.double_tap.emit(
                BokehDoubleTapEvent(
                    x=payload.get("x"),
                    y=payload.get("y"),
                    sx=payload.get("sx"),
                    sy=payload.get("sy"),
                    raw=payload,
                )
            )
        elif kind == "selection":
            self._events.selection.emit(
                BokehSelectionEvent(
                    geometry=payload.get("geometry"),
                    raw=payload,
                )
            )
        elif kind == "ranges_update":
            self._events.ranges_update.emit(
                BokehRangesUpdateEvent(
                    x0=payload.get("x0"),
                    x1=payload.get("x1"),
                    y0=payload.get("y0"),
                    y1=payload.get("y1"),
                    raw=payload,
                )
            )


# Module-level set tracking instrumented figures by id(), so we don't stack
# duplicate CustomJS callbacks across repeated `to_html()` calls on the same
# figure. Lives at module scope because we can't always setattr on a Bokeh
# model (slots, validation, etc.).
_INSTRUMENTED_IDS: set[int] = set()
