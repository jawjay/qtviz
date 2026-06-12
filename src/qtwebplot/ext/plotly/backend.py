"""PlotlyBackend — produces Plotly HTML, wires Plotly events to the bridge,
and exposes Plotly verbs as Python methods.

Usage:
    from qtwebplot import PlotView
    from qtwebplot.ext.plotly import PlotlyBackend

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

from qtwebplot.backend import PlotBackend
from qtwebplot.ext.plotly._runtime import PLOTLY_JS
from qtwebplot.ext.plotly.events import (
    PlotlyClickEvent,
    PlotlyEvents,
    PlotlyHoverEvent,
    PlotlyPoint,
    PlotlyRelayoutEvent,
    PlotlySelectionEvent,
)

if TYPE_CHECKING:
    from qtwebplot.core import WebBridgeView


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

    # ── PlotBackend protocol ─────────────────────────────────────────────
    def to_html(self) -> str:
        import plotly.graph_objects as go
        from plotly.io import to_html

        fig = self._figure if self._figure is not None else go.Figure()
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
        from plotly.io import to_json
    except ImportError as e:
        raise RuntimeError("plotly is required for PlotlyBackend") from e

    raw = json.loads(to_json(figure, validate=False))
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
