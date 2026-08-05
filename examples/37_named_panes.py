"""Named panes — address every subplot by name, before and after render
([D145]–[D151], design/pane-handles.md).

The mosaic's **list form** names panes with real words (`"price"`,
`"volume"`, `"depth"`); repeated labels span cells like `subplot_mosaic`.
`link_x="col"` keeps each grid column time-aligned (a spanning pane joins
every column it covers). Downstream, the same names address the live render —
the "Axes of qtviz":

    view.pane("price").set_range(x=(18, 30))   # programmatic zoom; the
                                               # linked "volume" pane follows
    view.pane("depth").autorange()
    view.pane("price").export("price.png")     # just that pane
    view.on(qv.RangeEvent, cb, pane="price")   # pane-scoped events
    view.set_root(view.root.with_pane("depth", other))  # declarative swap

Run:
    uv run python examples/37_named_panes.py
"""

from __future__ import annotations

import numpy as np

import qtviz as qv

rng = np.random.default_rng(7)
t = np.linspace(0.0, 30.0, 600)
price = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, t.size)))
volume = np.abs(rng.normal(1.0, 0.4, t.size)) * (1 + 0.5 * np.sin(t / 3))
returns = {"r": np.diff(np.log(price)) * 100}

panes = {
    "price": (qv.Curve({"t": t, "p": price}, x="t", y="p", label="price")
              * qv.HLine(float(price.mean()), line_style="dashed", label="mean")
              ).opts(title="Price", x="t [s]"),
    "volume": qv.Area({"t": t, "v": volume}, x="t", y="v", alpha=0.6)
              .opts(title="Volume", x="t [s]"),
    "depth": qv.Histogram(returns, value="r", bins="fd")
             .opts(title="Returns (%)"),
}

root = qv.Layout.mosaic(
    [["price", "depth"],
     ["volume", "depth"]],          # multi-char labels; "depth" spans both rows
    panes,
    options=qv.LayoutOptions(
        link_x="col",               # the price/volume column pans together
        width_ratios=[1.6, 1.0],
        title="Named panes: mosaic labels drive layout, linking, and view.pane()",
    ),
)


def build() -> qv.View:
    view = qv.View(root, backend="pyqtgraph")
    # Downstream use of a named pane: zoom "price" programmatically — the
    # column link carries "volume" along; "depth" (its own column) stays put.
    view.pane("price").set_range(x=(18.0, 30.0))
    return view


def main() -> None:
    view = build()
    view.on(qv.RangeEvent,
            lambda e: print(f"[{e.pane}] x={e.x[0]:.2f}..{e.x[1]:.2f}"),
            pane="price", throttle_ms=200)
    qv.show(view, title="qtviz — named panes", size=(1100, 620))


if __name__ == "__main__":
    main()
