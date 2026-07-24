"""Live telemetry — the 0.6 "live & linked" dashboard ([D76]–[D78]).

Three panels, ~90 lines:

  1. **Live** — a `qv.stream` with a 2 000-row rolling window; a QTimer (stand-in
     for your acquisition thread — `append` is thread-safe) feeds batches and the
     Curve updates *in place* at interactive rates, next to a dashed alarm line.
  2. **History** — 400k accumulated samples, datashaded; re-aggregates as you zoom.
  3. **Detail** — Shift-drag the history panel: the raster brush emits a
     `SelectEvent` with true source-row indices; a `Signal` re-renders this panel
     with just the brushed samples.

Run:
    uv run python examples/34_streaming_telemetry.py
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSplitter

import qtviz as qv

RNG = np.random.default_rng(3)


def _batch(t0: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    t = t0 + np.arange(n) / 50.0
    v = 3.0 * np.sin(2 * np.pi * t / 8.0) + RNG.normal(0.0, 0.4, n)
    return t, v


def build():
    theme = qv.Theme.dark()

    # 1 — the live feed: a rolling ring buffer any thread may append to
    feed = qv.stream({"t": float, "v": float}, window=2_000)
    t_seed, v_seed = _batch(0.0, 200)
    feed.append(t=t_seed, v=v_seed)
    live = qv.Overlay(
        [qv.Curve(feed, x="t", y="v", label="live"),
         qv.HLine(3.0, line_style="dashed", alpha=0.7, label="alarm")],
        options=qv.OverlayOptions(title="Live feed (rolling 2k)"),
    )

    # 2 — the accumulated history, datashaded
    t_hist, v_hist = _batch(-36_000.0, 400_000)
    history = {"t": t_hist, "v": v_hist}
    shaded = qv.Scatter(history, x="t", y="v", scale="datashader")
    main_view = qv.View(qv.Layout([live, shaded], options=qv.LayoutOptions(rows=2)),
                        theme=theme)

    # 3 — brush the raster → true source rows → a Signal drives the detail panel
    selection = qv.signal(np.array([], dtype=int))
    detail_view = qv.View(qv.derived(lambda: _detail(history, selection.get())),
                          theme=theme)
    main_view.on(qv.SelectEvent,
                 lambda e: e.source_id == shaded.id
                 and selection.set(np.asarray(e.indices, dtype=int)))

    splitter = QSplitter()
    splitter.addWidget(main_view)
    splitter.addWidget(detail_view)

    # the feeder — swap for your acquisition thread; feed.append is thread-safe
    clock = {"t": 4.0}

    def tick() -> None:
        t, v = _batch(clock["t"], 25)
        clock["t"] = float(t[-1]) + 1.0 / 50.0
        feed.append(t=t, v=v)

    timer = QTimer(splitter)
    timer.setInterval(33)  # ~30 Hz batches
    timer.timeout.connect(tick)
    return splitter, main_view, detail_view, feed, timer


def _detail(history: dict, idx: np.ndarray):
    if len(idx) == 0:
        return qv.Text(0.5, 0.5, "Shift-drag the history panel to inspect a region")
    return qv.Scatter({"t": history["t"][idx], "v": history["v"][idx]},
                      x="t", y="v", color="#ff5b5b", size=4)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    splitter, _main, _detail_v, _feed, timer = build()
    timer.start()
    splitter.resize(1200, 700)
    splitter.setWindowTitle("qtviz — live & linked telemetry")
    splitter.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
