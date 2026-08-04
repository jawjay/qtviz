"""Reactive crossfilter — brush one view to filter another (spec §9).

The whole linked-brushing story falls out of three pieces with no special
machinery: a `Signal` holds the brushed selection, a left `View` writes it on
every `SelectEvent`, and a right `View` is built from a `derived` that reads the
signal — so brushing the left panel re-renders the right with just those rows.

Reactivity lives at the **View root** (a `Signal[Node]`), so Elements stay pure;
the right panel's node is rebuilt fresh on each change. Native pyqtgraph, fully
offline — no webengine.

  - **Shift + drag** on the left panel to rubber-band a selection.
  - The right panel redraws those rows (x vs z); empty selection shows all, greyed.

Run:
    uv run python examples/21_reactive_crossfilter.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import qtviz as qv


def _panel(title: str, view: QWidget) -> QWidget:
    w = QWidget()
    box = QVBoxLayout(w)
    box.addWidget(QLabel(title))
    box.addWidget(view)
    return w


def build():
    rng = np.random.default_rng(0)
    n = 3000
    data = {"x": rng.normal(size=n), "y": rng.normal(size=n), "z": rng.normal(size=n)}

    selection = qv.signal(None)  # row indices brushed on the left panel

    left = qv.View(qv.Scatter(data, x="x", y="y", size=4))
    left.on(qv.SelectEvent, lambda e: selection.set(e.indices))

    def right_node():
        idx = selection.get()
        if not idx:
            return qv.Scatter(data, x="x", y="z", size=3, color="#bbbbbb")
        rows = {k: np.asarray(v)[idx] for k, v in data.items()}
        return qv.Scatter(rows, x="x", y="z", size=6, color="#ff5b5b")

    right = qv.View(qv.derived(right_node))

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addWidget(_panel("brush here (Shift+drag) — x vs y", left))
    layout.addWidget(_panel("selected rows — x vs z", right))
    return container


def main() -> None:
    # [D134]: the Qt ceremony is gone
    qv.show(build(), title="qtviz — reactive crossfilter", size=(1040, 540))


if __name__ == "__main__":
    main()
