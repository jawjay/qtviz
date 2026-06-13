"""Crossfilter dashboard — 4 coordinated plots over a shared dataset.

A more realistic linked-plot example than `linked_plots.py`. Four plots
share one synthetic dataset; selecting in any source plot drives a
re-render of all the others using the filtered subset.

Layout (2x2):
    ┌─────────────────────────┬─────────────────────────┐
    │  Plotly scatter         │  Bokeh bar chart        │
    │  (x vs y, by category)  │  (count per category)   │
    │  source: box-select     │  source: tap a bar      │
    ├─────────────────────────┼─────────────────────────┤
    │  Plotly histogram       │  Bokeh time series       │
    │  (filtered values)      │  (filtered values)       │
    │  read-only              │  read-only               │
    └─────────────────────────┴─────────────────────────┘

Run:
    uv sync --extra plotly --extra bokeh --extra dev
    uv run python examples/dashboard_crossfilter.py

# What this example is for

This is a *stress-test* of the current architecture, not a finished
feature. It surfaces patterns that suggest concrete future capability.
Each pattern is called out inline; collected here for review:

1. **Broadcast handler shape.** `link(source, event, to=[1,2,3], handler=...)`
   calls `handler(target_backend, payload)` *per target*. For "parse the
   event once, redraw every other plot from a derived state" we need a
   broadcast variant: `link(source, event, on=handler)` where `handler`
   gets the payload once. Until we have it, we wire raw `view.received`
   directly (search this file for `# pattern: broadcast`).

2. **Shared data model.** The dashboard owns a `Dataset` and a `Filter`,
   then per-plot `_build_*` functions recompute from those. This is the
   crossfilter / dc.js / Tableau-extract pattern. A `qtwebplot.data.Dataset`
   + `Filter` abstraction with subscribers would remove the per-plot
   "is the source / is the target" bookkeeping in every dashboard.

3. **Source/target exclusion to avoid update loops.** When the scatter
   triggers a filter, we explicitly skip the scatter when rebuilding to
   avoid a `react`-induced selection-cleared event from echoing back.
   A `view.send_quiet(...)` or a "this update is in-flight" lock at the
   bridge level would let plots react to programmatic updates differently
   from user events.

4. **Coordinate-to-category mapping.** Bokeh's `Tap` event reports a
   numeric x for a categorical axis; we manually round and look up the
   category. A first-class `bokeh.selection_change` event (CDS
   `selected.indices`) would be more honest.

5. **Plotly trace-index ↔ dataset-index mapping.** We use one trace with
   a marker.color array so `point_index` is the dataset index. Multiple
   traces (one per category) would let the legend toggle, but force us
   to maintain trace-to-dataset index tables. Hints at a need for a
   "labelled data source" wrapper.

6. **Visual: highlight vs filter.** Showing the unselected subset dim
   rather than dropping it is much nicer UX but requires *every plot* to
   produce a "highlighted vs background" rendering. A `Theme.dim` color
   plus a `Filter.opacity_array(n)` helper would standardize this.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass

from bokeh.models import ColumnDataSource
from bokeh.plotting import figure as bokeh_figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import plotly.graph_objects as go

from qtwebplot import PlotGrid
from qtwebplot.ext.bokeh import BokehBackend
from qtwebplot.ext.plotly import PlotlyBackend


# ── data model ───────────────────────────────────────────────────────────────


CATEGORIES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
CATEGORY_COLORS = {
    "Alpha":   "#1f77b4",
    "Bravo":   "#ff7f0e",
    "Charlie": "#2ca02c",
    "Delta":   "#d62728",
    "Echo":    "#9467bd",
}
DIM_OPACITY = 0.12
LIVE_OPACITY = 1.0


@dataclass
class Dataset:
    """Parallel arrays — friendly to both Plotly and Bokeh."""

    x: list[float]
    y: list[float]
    category: list[str]
    value: list[float]

    @property
    def n(self) -> int:
        return len(self.x)

    @classmethod
    def synthetic(cls, n: int = 600, seed: int = 42) -> "Dataset":
        rng = random.Random(seed)
        # One Gaussian cluster per category.
        centers = {
            "Alpha":   (-2.0, -2.0),
            "Bravo":   ( 2.0, -2.0),
            "Charlie": ( 2.0,  2.0),
            "Delta":   (-2.0,  2.0),
            "Echo":    ( 0.0,  0.0),
        }
        x, y, cat, val = [], [], [], []
        for i in range(n):
            c = CATEGORIES[i % len(CATEGORIES)]
            cx, cy = centers[c]
            x.append(rng.gauss(cx, 0.9))
            y.append(rng.gauss(cy, 0.9))
            cat.append(c)
            val.append(abs(rng.gauss(50, 15)))
        return cls(x=x, y=y, category=cat, value=val)


@dataclass
class Filter:
    """A subset of dataset indices, or None for `all`."""

    indices: set[int] | None = None

    @property
    def is_all(self) -> bool:
        return self.indices is None

    def includes(self, i: int) -> bool:
        return self.indices is None or i in self.indices

    def count(self, total: int) -> int:
        return total if self.indices is None else len(self.indices)

    def opacity_array(self, n: int) -> list[float]:
        if self.indices is None:
            return [LIVE_OPACITY] * n
        return [LIVE_OPACITY if i in self.indices else DIM_OPACITY for i in range(n)]


# ── plot builders ────────────────────────────────────────────────────────────


def build_scatter_figure(ds: Dataset, flt: Filter) -> go.Figure:
    """One trace, per-point color & opacity. point_index == dataset index."""
    colors = [CATEGORY_COLORS[c] for c in ds.category]
    opacities = flt.opacity_array(ds.n)
    fig = go.Figure(
        data=[
            go.Scatter(
                x=ds.x,
                y=ds.y,
                mode="markers",
                marker=dict(
                    color=colors,
                    opacity=opacities,
                    size=8,
                    line=dict(width=0),
                ),
                hovertemplate="cat=%{customdata}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
                customdata=ds.category,
                name="points",
                selectedpoints=None,
            )
        ]
    )
    fig.update_layout(
        title="Box-select to filter",
        margin=dict(l=40, r=20, t=40, b=30),
        height=360,
        dragmode="select",
        showlegend=False,
    )
    return fig


def build_bars_figure(ds: Dataset, flt: Filter):
    counts = _counts_by_category(ds, flt)
    src = ColumnDataSource(
        data={
            "category": list(CATEGORIES),
            "count": [counts[c] for c in CATEGORIES],
            "color": [CATEGORY_COLORS[c] for c in CATEGORIES],
        },
        name="bars_src",
    )
    p = bokeh_figure(
        x_range=list(CATEGORIES),
        height=360,
        sizing_mode="stretch_width",
        tools="tap,reset",
        title="Tap a bar to filter to that category",
        toolbar_location="right",
    )
    p.vbar(x="category", top="count", width=0.7, source=src, fill_color="color", line_color=None)
    p.y_range.start = 0
    p.xaxis.major_label_orientation = 0
    return p


def build_hist_figure(ds: Dataset, flt: Filter) -> go.Figure:
    # Filtered values, by category, stacked.
    traces = []
    for c in CATEGORIES:
        vs = [ds.value[i] for i in range(ds.n) if ds.category[i] == c and flt.includes(i)]
        traces.append(
            go.Histogram(
                x=vs,
                name=c,
                marker_color=CATEGORY_COLORS[c],
                opacity=0.85,
                xbins=dict(start=0, end=120, size=5),
            )
        )
    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="stack",
        title=f"Value distribution ({flt.count(ds.n)} pts)",
        margin=dict(l=40, r=20, t=40, b=30),
        height=360,
        showlegend=True,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def build_timeseries_figure(ds: Dataset, flt: Filter):
    src = ColumnDataSource(
        data={
            "i": list(range(ds.n)),
            "value": list(ds.value),
            "color": [CATEGORY_COLORS[c] for c in ds.category],
            "alpha": flt.opacity_array(ds.n),
        },
        name="ts_src",
    )
    p = bokeh_figure(
        height=360,
        sizing_mode="stretch_width",
        tools="pan,wheel_zoom,box_zoom,reset",
        title="Value vs index",
        toolbar_location="right",
    )
    p.scatter(x="i", y="value", source=src, color="color", alpha="alpha", size=6, name="ts_dots")
    return p


def _counts_by_category(ds: Dataset, flt: Filter) -> dict[str, int]:
    counts = dict.fromkeys(CATEGORIES, 0)
    for i in range(ds.n):
        if flt.includes(i):
            counts[ds.category[i]] += 1
    return counts


# ── dashboard ────────────────────────────────────────────────────────────────


class Dashboard(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot — crossfilter dashboard")
        self.resize(1280, 880)

        self.dataset = Dataset.synthetic(n=600, seed=42)
        self.filter = Filter()

        # ── backends ────
        self.scatter_b = PlotlyBackend(build_scatter_figure(self.dataset, self.filter))
        self.bars_b = BokehBackend(build_bars_figure(self.dataset, self.filter))
        self.hist_b = PlotlyBackend(build_hist_figure(self.dataset, self.filter))
        self.ts_b = BokehBackend(build_timeseries_figure(self.dataset, self.filter))

        self.grid = PlotGrid(
            [self.scatter_b, self.bars_b, self.hist_b, self.ts_b],
            cols=2,
            spacing=6,
        )

        # ── status & reset ────
        self.status = QLabel()
        self.reset_btn = QPushButton("Clear filter")
        self.reset_btn.clicked.connect(self._reset)
        bar = QHBoxLayout()
        bar.addWidget(self.status)
        bar.addStretch(1)
        bar.addWidget(self.reset_btn)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.addLayout(bar)
        root.addWidget(self.grid, 1)
        self.setCentralWidget(central)

        self._update_status()

        # ── coordination wiring ────
        # pattern: broadcast — we want "one event → rebuild every other plot."
        # link() iterates per-target, which is wrong shape for that. So we
        # listen on view.received directly. Open question: should layouts
        # ship a `link_broadcast(source, event, on=handler)` for this?
        self.grid.views[0].received.connect(self._on_scatter_event)
        self.grid.views[1].received.connect(self._on_bars_event)
        # Hist + timeseries are read-only views.

    # ── event handlers ──────────────────────────────────────────────────
    def _on_scatter_event(self, name: str, payload: object) -> None:
        if name != "plotly.selection":
            return
        pts = (payload or {}).get("points") or []
        if not pts:
            # Empty selection = double-click to clear; treat as reset.
            self._set_filter(Filter(), source=self.scatter_b)
            return
        # single trace, so point_index == dataset index.
        indices = {p.get("point_index") for p in pts if p.get("point_index") is not None}
        self._set_filter(Filter(indices), source=self.scatter_b)

    def _on_bars_event(self, name: str, payload: object) -> None:
        if name != "bokeh.tap":
            return
        x = (payload or {}).get("x")
        # Bokeh's Tap on a categorical axis can report either the string
        # category or a numeric synthetic coordinate. Handle both.
        category: str | None = None
        if isinstance(x, str) and x in CATEGORY_COLORS:
            category = x
        elif isinstance(x, (int, float)):
            idx = int(round(x))
            if 0 <= idx < len(CATEGORIES):
                category = CATEGORIES[idx]
        if category is None:
            return
        indices = {i for i in range(self.dataset.n) if self.dataset.category[i] == category}
        self._set_filter(Filter(indices), source=self.bars_b)

    def _reset(self) -> None:
        self._set_filter(Filter(), source=None)

    # ── state propagation ───────────────────────────────────────────────
    def _set_filter(self, new_filter: Filter, *, source) -> None:
        """Update the central filter and re-render every plot EXCEPT the
        source. Skipping the source avoids "I just received my own state
        echoed back" loops when react/patch resets selection."""
        self.filter = new_filter

        # pattern: source-exclusion. A first-class "in-flight" lock at the
        # bridge level would let us drop this manual check.
        if source is not self.scatter_b:
            self.scatter_b.react(build_scatter_figure(self.dataset, self.filter))
        if source is not self.bars_b:
            counts = _counts_by_category(self.dataset, self.filter)
            self.bars_b.patch(
                "bars_src",
                {
                    "category": list(CATEGORIES),
                    "count": [counts[c] for c in CATEGORIES],
                    "color": [CATEGORY_COLORS[c] for c in CATEGORIES],
                },
            )
        if source is not self.hist_b:
            self.hist_b.react(build_hist_figure(self.dataset, self.filter))
        if source is not self.ts_b:
            self.ts_b.patch(
                "ts_src",
                {
                    "i": list(range(self.dataset.n)),
                    "value": list(self.dataset.value),
                    "color": [CATEGORY_COLORS[c] for c in self.dataset.category],
                    "alpha": self.filter.opacity_array(self.dataset.n),
                },
            )

        self._update_status()

    def _update_status(self) -> None:
        if self.filter.is_all:
            self.status.setText(f"Showing all {self.dataset.n} points.")
        else:
            self.status.setText(
                f"Filtered: {self.filter.count(self.dataset.n)} / {self.dataset.n} points."
            )


def main() -> int:
    app = QApplication(sys.argv)
    win = Dashboard()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
