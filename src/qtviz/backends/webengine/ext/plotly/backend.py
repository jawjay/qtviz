"""PlotlyBackend — produces Plotly HTML, wires Plotly events to the bridge,
and exposes Plotly verbs as Python methods.

Usage:
    from qtviz.backends.webengine import PlotView
    from qtviz.backends.webengine.ext.plotly import PlotlyBackend

    backend = PlotlyBackend(fig)
    view = PlotView(backend)
    view.show()

    # Plotly verbs live on the backend, not the view:
    backend.relayout({"title.text": "new"})
    backend.events.hover.connect(lambda e: print(e.points))
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from qtviz.backends.webengine.backend import PlotBackend
from qtviz.backends.webengine.ext.plotly._runtime import PLOTLY_JS
from qtviz.backends.webengine.ext.plotly.events import (
    PlotlyClickEvent,
    PlotlyEvents,
    PlotlyHoverEvent,
    PlotlyPoint,
    PlotlyRelayoutEvent,
    PlotlySelectionEvent,
)

if TYPE_CHECKING:
    from qtviz.backends.webengine.core import WebBridgeView
    from qtviz.backends.webengine.theme import Theme


_PLOT_DIV_ID = "qtwp-plot"


class PlotlyBackend(PlotBackend):
    """Hosts a Plotly figure in a `PlotView` (or any `WebBridgeView`)."""

    def __init__(
        self,
        figure: Any = None,
        *,
        plotlyjs: str = "cdn",
    ) -> None:
        self._figure = figure
        self._plotlyjs = plotlyjs
        self._view: WebBridgeView | None = None
        self._events = PlotlyEvents()
        self._theme: Theme | None = None

    # ── PlotBackend protocol ─────────────────────────────────────────────
    def to_html(self) -> str:
        import plotly.graph_objects as go
        from plotly.io import to_html

        # Coerce a dict figure (qtviz's Element renderers build dicts) into a
        # go.Figure so Plotly's base64 typed-array encoder engages for numpy
        # arrays (W5.1a) — a raw dict, even with numpy, serializes as JSON text.
        src = self._figure
        fig = src if isinstance(src, go.Figure) else go.Figure(src or {})
        if self._theme is not None:
            fig.update_layout(template=_plotly_template_from(self._theme))
        return to_html(
            fig,
            include_plotlyjs=self._plotlyjs,
            full_html=True,
            div_id=_PLOT_DIV_ID,
            config={"responsive": True},
        )

    def js_runtime(self) -> str:
        # Prepend a small line that tells our JS which div to target.
        return f"window.qtwebplot = window.qtwebplot || {{}};\nwindow.qtwebplot.plot_div_id = '{_PLOT_DIV_ID}';\n" + PLOTLY_JS

    def on_attach(self, view: WebBridgeView) -> None:
        self._view = view
        view.received.connect(self._on_message)

    def on_detach(self) -> None:
        if self._view is not None:
            try:
                self._view.received.disconnect(self._on_message)
            except (RuntimeError, TypeError):
                pass
        self._view = None

    def set_figure(self, figure: Any) -> None:
        self._figure = figure

    def apply_theme(self, theme: Theme) -> None:
        """Apply theme to the current figure via Plotly's template system.

        Re-applied on every `to_html()` so subsequent `set_figure` calls
        inherit it as long as the backend is alive.
        """
        self._theme = theme

    # ── Plotly verbs (use the generic bridge transport) ──────────────────
    @property
    def events(self) -> PlotlyEvents:
        return self._events

    @property
    def figure(self) -> Any:
        return self._figure

    def react(self, figure: Any) -> None:
        """Replace the live figure in-place — no page reload."""
        self._figure = figure
        payload = _figure_to_payload(figure)
        self._require_view().send("plotly.react", payload)

    def restyle(self, update: dict, indices: list[int] | None = None) -> None:
        self._require_view().send("plotly.restyle", {"update": update, "indices": indices})

    def relayout(self, update: dict) -> None:
        self._require_view().send("plotly.relayout", {"update": update})

    def extend_traces(
        self,
        update: dict,
        indices: list[int],
        max_points: int | None = None,
    ) -> None:
        self._require_view().send(
            "plotly.extend",
            {"update": update, "indices": indices, "max_points": max_points},
        )

    def resize(self) -> None:
        self._require_view().send("plotly.resize", None)

    # ── internals ────────────────────────────────────────────────────────
    def _require_view(self) -> WebBridgeView:
        if self._view is None:
            raise RuntimeError(
                "PlotlyBackend is not attached to a view. "
                "Did you forget to pass it to PlotView()?"
            )
        return self._view

    def _on_message(self, name: str, payload: object) -> None:
        if not name.startswith("plotly."):
            return
        if not isinstance(payload, dict):
            return
        kind = name.split(".", 1)[1]
        if kind == "hover":
            self._events.hover.emit(_build_hover(payload))
        elif kind == "unhover":
            self._events.unhover.emit(_build_hover(payload))
        elif kind == "click":
            self._events.click.emit(_build_click(payload))
        elif kind == "selection":
            self._events.selection.emit(_build_selection(payload))
        elif kind == "relayout":
            update = payload.get("update", {}) or {}
            self._events.relayout.emit(PlotlyRelayoutEvent(update=update, raw=payload))


def _figure_to_payload(figure: Any) -> dict:
    """Translate a Plotly Figure to a JSON-friendly {data, layout, config} dict."""
    try:
        import plotly.graph_objects as go
        from plotly.io import to_json
    except ImportError as e:
        raise RuntimeError("plotly is required for PlotlyBackend") from e

    fig = figure if isinstance(figure, go.Figure) else go.Figure(figure)  # base64 (W5.1a)
    raw = json.loads(to_json(fig, validate=False))
    return {
        "data": raw.get("data", []),
        "layout": raw.get("layout", {}),
        "config": {},
    }


def _points_from(payload: dict) -> list[PlotlyPoint]:
    pts = payload.get("points") or []
    return [
        PlotlyPoint(
            trace_index=p.get("trace_index"),
            point_index=p.get("point_index"),
            x=p.get("x"),
            y=p.get("y"),
            z=p.get("z"),
            text=p.get("text"),
            curve_number=p.get("curve_number"),
        )
        for p in pts
    ]


def _build_hover(payload: dict) -> PlotlyHoverEvent:
    return PlotlyHoverEvent(points=_points_from(payload), raw=payload)


def _build_click(payload: dict) -> PlotlyClickEvent:
    return PlotlyClickEvent(points=_points_from(payload), raw=payload)


def _build_selection(payload: dict) -> PlotlySelectionEvent:
    return PlotlySelectionEvent(
        points=_points_from(payload),
        range=payload.get("range"),
        raw=payload,
    )


def _plotly_template_from(theme: "Theme") -> dict:
    """Translate a qtwebplot Theme into a Plotly template dict."""
    return {
        "layout": {
            "paper_bgcolor": theme.background,
            "plot_bgcolor": theme.background,
            "font": {"color": theme.foreground, "family": theme.font_family},
            "title": {"font": {"color": theme.foreground}},
            "colorway": list(theme.palette),
            "xaxis": {
                "gridcolor": theme.grid,
                "linecolor": theme.foreground,
                "zerolinecolor": theme.grid,
                "tickfont": {"color": theme.foreground},
                "title": {"font": {"color": theme.foreground}},
            },
            "yaxis": {
                "gridcolor": theme.grid,
                "linecolor": theme.foreground,
                "zerolinecolor": theme.grid,
                "tickfont": {"color": theme.foreground},
                "title": {"font": {"color": theme.foreground}},
            },
            "legend": {"font": {"color": theme.foreground}},
        }
    }
