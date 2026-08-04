"""Market analytics — price, moving averages, Bollinger bands, and volume.

A standard technical-analysis layout over a synthetic equity series:

  - a **price** curve with **20- and 50-day moving averages** overlaid;
  - a **Bollinger band** (20-day mean ± 2·σ) as a filled `Spread` behind the price;
  - a **volume** bar panel beneath, sharing the price panel's X axis (`link_x`).

Brush the price panel (Shift-drag) to mark a window of trading days; the `SelectEvent`
reports the day indices a real screener would zoom or compute stats on. The X axis is a
numeric trading-day index (qtviz does not yet ship a calendar/date axis).

Run:
    uv run python examples/27_market_analytics.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import qtviz as qv


def _ohlc() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    n = 320
    day = np.arange(n, dtype=float)
    returns = rng.normal(0.0006, 0.018, n)
    price = 100 * np.exp(np.cumsum(returns))          # geometric random walk
    volume = rng.gamma(2.0, 1.0, n) * 1e6 * (1 + 0.4 * np.abs(returns) / 0.018)
    df = pd.DataFrame({"day": day, "price": price, "volume": volume})
    df["ma20"] = df["price"].rolling(20, min_periods=1).mean()
    df["ma50"] = df["price"].rolling(50, min_periods=1).mean()
    sd20 = df["price"].rolling(20, min_periods=1).std().fillna(0.0)
    df["boll_lo"] = df["ma20"] - 2 * sd20
    df["boll_hi"] = df["ma20"] + 2 * sd20
    return df


def build(theme: qv.Theme | None = None):
    df = _ohlc()

    band = qv.Spread(df, x="day", lo="boll_lo", hi="boll_hi", color="#4b6584", alpha=0.25)
    price = qv.Curve(df, x="day", y="price", color="#e8eaed", line_width=1.6)
    ma20 = qv.Curve(df, x="day", y="ma20", color="#f7b500", line_width=1.4)
    ma50 = qv.Curve(df, x="day", y="ma50", color="#26de81", line_width=1.4, line_style="dashed")
    chart = band * price * ma20 * ma50

    volume = qv.Bars(df, x="day", y="volume", color="#5b7cfa")

    layout = qv.Layout([chart, volume], options=qv.LayoutOptions(rows=2, link_x=True))
    view = qv.View(layout, theme=theme or qv.Theme.dark())

    def on_window(e: qv.SelectEvent) -> None:
        x0, x1 = e.bounds[0], e.bounds[2]
        print(f"window: {len(e.indices)} days (x {x0:.0f}..{x1:.0f})")

    view.on(qv.SelectEvent, on_window)
    return view


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(1100, 660)
    view.setWindowTitle("qtviz — market analytics")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
