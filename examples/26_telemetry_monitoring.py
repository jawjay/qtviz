"""Sensor telemetry monitoring — a rolling baseline, a tolerance band, and flagged anomalies.

A realistic "is this signal behaving?" view over noisy instrument data (here, a
diurnal temperature trace with a few injected faults). The pipeline is the kind you
actually run:

  1. a centered rolling mean is the **expected baseline**;
  2. a ±4·σ rolling band is the **tolerance envelope** (a `Spread` — it tracks the
     baseline, so it is data, not chrome);
  3. samples outside the band are **anomalies** (a red `Scatter` on top);
  4. a second, X-linked panel plots the **residual** (signal − baseline) — derived on
     the fly with a qtviz `Expression` — against *constant* reference chrome: a
     `Span` for the acceptable ±4·σ range and a dashed `HLine` at zero (the 0.4
     annotation elements, [D70] — no more hand-rolled constant bands).

Labeled series aggregate into one legend per panel ([D60]).

Pan/zoom either panel and both move together (`link_x`). Shift-drag to brush a window;
the `SelectEvent` reports which samples you grabbed (what a real tool would drill into).

Run:
    uv run python examples/26_telemetry_monitoring.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import qtviz as qv


def _telemetry() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    t = np.linspace(0, 72, 1600)                      # 3 days, hours
    temp = 21 + 6 * np.sin(2 * np.pi * t / 24) + rng.normal(0, 0.7, t.size)
    temp[600:610] += 11                               # injected spike fault
    temp[1100:1115] -= 9                              # injected dropout fault
    df = pd.DataFrame({"t": t, "temp": temp})
    df["baseline"] = df["temp"].rolling(80, center=True, min_periods=1).mean()
    resid = df["temp"] - df["baseline"]
    # robust (MAD-based) noise estimate — a few large faults don't inflate it, so the
    # tolerance band stays a clean ribbon and real anomalies poke out of it.
    sigma = 1.4826 * np.median(np.abs(resid - np.median(resid)))
    tol = 4.0 * sigma
    df["lo"] = df["baseline"] - tol
    df["hi"] = df["baseline"] + tol
    df["flag"] = resid.abs() > tol
    return df, float(tol)


def build(theme: qv.Theme | None = None):
    df, tol = _telemetry()
    anomalies = df[df["flag"]]
    print(f"flagged {len(anomalies)} anomalous samples of {len(df)}")

    band = qv.Spread(df, x="t", y_lo="lo", y_hi="hi", color="#3a6ea5", alpha=0.25,
                     label="tolerance")
    signal = qv.Curve(df, x="t", y="temp", color="#9ecbff", line_width=1.0, label="signal")
    baseline = qv.Curve(df, x="t", y="baseline", color="#ffb454", line_width=2.0,
                        label="baseline")
    faults = qv.Scatter(anomalies, x="t", y="temp", color="#ff5b5b", size=9,
                        label="anomalies")
    monitor = band * signal * baseline * faults                      # one overlaid axis

    # residual derived at render time from the columns — no precomputed column.
    # Its acceptable range is a *constant* → reference chrome, not data ([D70]):
    residual = (qv.Curve(df, x="t", y=qv.col("temp") - qv.col("baseline"),
                         color="#7bd47b", line_width=1.0, label="residual")
                * qv.Span(-tol, tol, color="#3a6ea5", alpha=0.18, label="±4σ")
                * qv.HLine(0.0, line_style="dashed", alpha=0.6))

    layout = qv.Layout([monitor, residual], options=qv.LayoutOptions(rows=2, link_x=True))
    view = qv.View(layout, theme=theme or qv.Theme.dark())
    view.on(qv.SelectEvent, lambda e: print(f"brushed {len(e.indices)} samples in {e.bounds}"))
    return view


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(1100, 640)
    view.setWindowTitle("qtviz — telemetry monitoring")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
