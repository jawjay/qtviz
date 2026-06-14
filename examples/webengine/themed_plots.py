"""Theme demo — Light / Dark / Auto-from-Qt-palette / Custom.

What this proves:
  - `Theme.from_qt_app()` derives colors and font from `QApplication.palette()`.
  - `Theme.light()` and `.dark()` ship as sensible defaults.
  - The same Theme dataclass styles both Plotly and Bokeh backends.
  - `view.set_theme(...)` re-applies live without recreating the view.

Run:
    uv sync --extra plotly --extra bokeh --extra dev
    uv run python examples/themed_plots.py
"""

from __future__ import annotations

import sys

import plotly.graph_objects as go
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure as bokeh_figure
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qtwebplot import PlotGrid, Theme
from qtwebplot.ext.bokeh import BokehBackend
from qtwebplot.ext.plotly import PlotlyBackend


def make_plotly() -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatter(x=list(range(15)), y=[i * 1.2 for i in range(15)], name="series 1"),
            go.Scatter(x=list(range(15)), y=[i * 0.7 + 3 for i in range(15)], name="series 2"),
            go.Scatter(x=list(range(15)), y=[i ** 0.6 * 2 for i in range(15)], name="series 3"),
        ]
    )
    fig.update_layout(title="Plotly", margin=dict(l=40, r=20, t=40, b=30), height=380)
    return fig


def make_bokeh():
    src = ColumnDataSource(
        data={"x": list(range(15)), "y1": [i * 1.2 for i in range(15)], "y2": [i * 0.7 + 3 for i in range(15)]},
        name="src",
    )
    p = bokeh_figure(height=380, sizing_mode="stretch_width", title="Bokeh")
    p.line("x", "y1", source=src, line_width=2, color="#1f77b4", legend_label="series 1")
    p.line("x", "y2", source=src, line_width=2, color="#ff7f0e", legend_label="series 2")
    p.scatter("x", "y1", source=src, size=6, color="#1f77b4")
    p.scatter("x", "y2", source=src, size=6, color="#ff7f0e")
    return p


class Demo(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtwebplot — theming")
        self.resize(1100, 700)

        # Auto-themed at construction from the current app palette.
        initial_theme = Theme.from_qt_app()
        self._grid = PlotGrid([], cols=2, spacing=6)
        # Build views with the initial theme.
        self._plotly_backend = PlotlyBackend(make_plotly())
        self._bokeh_backend = BokehBackend(make_bokeh())
        self._plotly_backend.apply_theme(initial_theme)
        self._bokeh_backend.apply_theme(initial_theme)
        self._grid.add(self._plotly_backend)
        self._grid.add(self._bokeh_backend)
        # Mark theme on each view so subsequent set_theme calls work.
        for v in self._grid.views:
            v._theme = initial_theme  # noqa: SLF001 — set after construction

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Theme:"))

        bg = QButtonGroup(self)
        for label, theme in (
            ("Auto (Qt palette)", None),
            ("Light", Theme.light()),
            ("Dark", Theme.dark()),
            ("High-contrast custom", Theme(
                background="#0a0a0a",
                foreground="#fdfdfd",
                grid="#202020",
                palette=("#00d2ff", "#ff5b6b", "#fcfc00", "#a0ff7c"),
                font_family="monospace",
            )),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, t=theme: self._apply(t))
            bg.addButton(btn)
            controls_layout.addWidget(btn)
        controls_layout.addStretch(1)

        info = QLabel(
            "The same Theme dataclass styles both backends. "
            "Switch the host app's appearance (macOS: System Settings → Appearance) "
            "and the Auto button picks up the change."
        )
        info.setWordWrap(True)

        root = QVBoxLayout()
        root.addLayout(controls_layout)
        root.addWidget(info)
        root.addWidget(self._grid, 1)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

    def _apply(self, theme: Theme | None) -> None:
        if theme is None:
            theme = Theme.from_qt_app()
        for view in self._grid.views:
            view.set_theme(theme)


def main() -> int:
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
