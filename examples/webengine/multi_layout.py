"""Expected-use demonstration of `PlotGrid`, `PlotTabs`, and `PlotSplitter`.

What this proves:
  - All three helpers accept an arbitrary mix of backends (Plotly + Bokeh
    in the same container).
  - `PlotGrid` is eager — every view builds at construction.
  - `PlotTabs(lazy=True)` only builds tabs as they're visited (watch for
    the per-tab "bridge ready" status appearing the first time you click
    each tab).
  - `PlotSplitter` is interactive — drag the handle between the two plots.
  - `add` / `remove` mutate the layout live without recreating the helper.

Run:
    uv sync --extra plotly --extra bokeh --extra dev
    uv run python examples/multi_layout.py
"""

from __future__ import annotations

import random
import sys

import plotly.graph_objects as go
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure as bokeh_figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from qtwebplot import PlotGrid, PlotTabs
from qtwebplot.ext.bokeh import BokehBackend
from qtwebplot.ext.plotly import PlotlyBackend
from qtwebplot.layouts import PlotSplitter


# ── figure factories ─────────────────────────────────────────────────────────


def plotly_scatter(seed: int, title: str) -> go.Figure:
    rng = random.Random(seed)
    n = 30
    fig = go.Figure(
        data=go.Scatter(
            x=list(range(n)),
            y=[rng.gauss(0, 1) for _ in range(n)],
            mode="lines+markers",
        )
    )
    fig.update_layout(title=title, margin=dict(l=40, r=20, t=40, b=30), height=300)
    return fig


def plotly_bar(seed: int, title: str) -> go.Figure:
    rng = random.Random(seed)
    labels = list("ABCDE")
    fig = go.Figure(data=go.Bar(x=labels, y=[rng.randint(1, 10) for _ in labels]))
    fig.update_layout(title=title, margin=dict(l=40, r=20, t=40, b=30), height=300)
    return fig


def bokeh_line(seed: int, title: str):
    rng = random.Random(seed)
    n = 30
    src = ColumnDataSource(
        data={"x": list(range(n)), "y": [rng.gauss(0, 1) for _ in range(n)]},
        name=f"src-{seed}",
    )
    p = bokeh_figure(height=300, sizing_mode="stretch_width", title=title)
    p.line("x", "y", source=src, line_width=2)
    p.scatter("x", "y", source=src, size=5)
    return p


# ── grid demo (eager) ────────────────────────────────────────────────────────


def build_grid_demo() -> QWidget:
    backends = [
        PlotlyBackend(plotly_scatter(0, "Plotly scatter")),
        BokehBackend(bokeh_line(1, "Bokeh line")),
        PlotlyBackend(plotly_bar(2, "Plotly bar")),
        BokehBackend(bokeh_line(3, "Bokeh line #2")),
    ]
    grid = PlotGrid(backends, cols=2, spacing=6)

    page = QWidget()
    page_layout = QVBoxLayout(page)

    info = QLabel(
        "PlotGrid: 4 mixed-backend plots. Use Add / Remove to mutate live."
    )
    info.setWordWrap(True)
    page_layout.addWidget(info)

    add_btn = QPushButton("Add another Plotly plot")
    remove_btn = QPushButton("Remove last")
    controls = QHBoxLayout()
    controls.addWidget(add_btn)
    controls.addWidget(remove_btn)
    controls.addStretch(1)
    page_layout.addLayout(controls)

    page_layout.addWidget(grid, 1)

    counter = {"n": 4}

    def on_add() -> None:
        counter["n"] += 1
        grid.add(PlotlyBackend(plotly_scatter(counter["n"], f"added #{counter['n']}")))

    def on_remove() -> None:
        if len(grid) > 0:
            grid.remove(len(grid) - 1)

    add_btn.clicked.connect(on_add)
    remove_btn.clicked.connect(on_remove)

    return page


# ── tabs demo (lazy) ─────────────────────────────────────────────────────────


def build_tabs_demo() -> QWidget:
    tabs = PlotTabs(
        {
            "Trends (Plotly)": PlotlyBackend(plotly_scatter(10, "Trends")),
            "Distribution (Plotly)": PlotlyBackend(plotly_bar(11, "Distribution")),
            "Live (Bokeh)": BokehBackend(bokeh_line(12, "Live")),
            "Spare (Plotly)": PlotlyBackend(plotly_scatter(13, "Spare")),
        },
        lazy=True,
    )

    page = QWidget()
    layout = QVBoxLayout(page)

    info = QLabel(
        "PlotTabs(lazy=True): tabs build their PlotView on first visit. "
        "Watch the 'views built' count — only the active tab is allocated."
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    built_label = QLabel()
    build_all_btn = QPushButton("Build all")

    def update_built_count() -> None:
        built_label.setText(f"views built: {len(tabs.views)} / {len(tabs)}")

    update_built_count()

    def on_build_all() -> None:
        tabs.build_all()
        update_built_count()

    build_all_btn.clicked.connect(on_build_all)
    tabs.tab_widget.currentChanged.connect(lambda _i: update_built_count())

    row = QHBoxLayout()
    row.addWidget(built_label)
    row.addStretch(1)
    row.addWidget(build_all_btn)
    layout.addLayout(row)

    layout.addWidget(tabs, 1)
    return page


# ── splitter demo ────────────────────────────────────────────────────────────


def build_splitter_demo() -> QWidget:
    splitter = PlotSplitter(
        [
            PlotlyBackend(plotly_scatter(20, "Left (Plotly)")),
            BokehBackend(bokeh_line(21, "Right (Bokeh)")),
        ],
        orientation=Qt.Horizontal,
    )
    splitter.setSizes([1, 1])

    page = QWidget()
    layout = QVBoxLayout(page)
    info = QLabel("PlotSplitter: drag the handle between the two plots.")
    layout.addWidget(info)
    layout.addWidget(splitter, 1)
    return page


# ── main window ──────────────────────────────────────────────────────────────


class Demo(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot — multi-visualization demo")
        self.resize(1100, 760)

        outer = QTabWidget(self)
        outer.addTab(build_grid_demo(), "Grid")
        outer.addTab(build_tabs_demo(), "Tabs (lazy)")
        outer.addTab(build_splitter_demo(), "Splitter")
        self.setCentralWidget(outer)


def main() -> int:
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
