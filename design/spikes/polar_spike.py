"""[D119] Option B spike — polar as a core transform, PUBLIC API ONLY.

The whole point of Option B: (θ, r) → (x, y) before the data seam, a
PolarGrid drawn from existing annotation elements, surface stays
rectilinear with aspect=1. If this file renders well on all three
backends *without touching src/*, the option is proven; whatever reads
badly is the honest cost list.

Renders polar_demo (spiral), polar_bar (wedges), radar — the three spike
deliverables — on pyqtgraph, matplotlib, webengine; writes PNGs.
"""

from __future__ import annotations

import sys

import numpy as np

import qtviz as qv


# ── the Option-B core pieces, prototyped at user level ───────────────────────
def pol2cart(theta, r):
    return r * np.cos(theta), r * np.sin(theta)


def polar_grid(r_max: float, *, rings: int = 4, spokes: int = 8,
               ring_labels: bool = True, spoke_labels: bool = True):
    """The [D70]-class `PolarGrid` chrome, from existing annotations:
    rings = Ellipse outlines, spokes = headless Arrows, labels = Text."""
    chrome = []
    radii = [r_max * i / rings for i in range(1, rings + 1)]
    for rr in radii:
        chrome.append(qv.Ellipse(0.0, 0.0, rr, rr, alpha=0.35))
    for k in range(spokes):
        th = 2.0 * np.pi * k / spokes
        x1, y1 = float(r_max * np.cos(th)), float(r_max * np.sin(th))
        chrome.append(qv.Arrow(0.0, 0.0, x1, y1, head="none", alpha=0.25))
        if spoke_labels:
            deg = int(round(np.degrees(th)))
            chrome.append(qv.Text(1.12 * x1, 1.12 * y1, f"{deg}°",
                                  halign="center"))
    if ring_labels:
        for rr in radii:
            chrome.append(qv.Text(0.04 * r_max, rr, f"{rr:g}", halign="left"))
    node = chrome[0]
    for c in chrome[1:]:
        node = node * c
    return node


def wedge(theta0, theta1, r0, r1, n=16):
    """An annulus sector outline (polar bar) as literal Polygon points."""
    ts = np.linspace(theta0, theta1, n)
    outer = [(r1 * np.cos(t), r1 * np.sin(t)) for t in ts]
    inner = [(r0 * np.cos(t), r0 * np.sin(t)) for t in ts[::-1]]
    return [(float(x), float(y)) for x, y in outer + inner]


def _frame(node, r_max, title):
    pad = 1.3 * r_max
    return node.opts(title=title, aspect=1.0, grid=False,
                     x=qv.AxisSpec(lim=(-pad, pad), ticks=()),
                     y=qv.AxisSpec(lim=(-pad, pad), ticks=()))


# ── the three spike figures ──────────────────────────────────────────────────
def make_polar_demo():
    """mpl gallery `polar_demo`: the r = θ spiral."""
    r = np.arange(0.0, 2.0, 0.01)
    theta = 2.0 * np.pi * r
    x, y = pol2cart(theta, r)
    curve = qv.Curve({"x": x, "y": y}, x="x", y="y", line_width=2.0)
    return _frame(polar_grid(2.0) * curve, 2.0, "polar_demo (r = θ spiral)")


def make_polar_bar():
    """mpl gallery polar bar: N wedges with random heights."""
    rng = np.random.default_rng(19680801)
    n = 20
    heights = 10.0 * rng.random(n)
    node = polar_grid(10.0, rings=5, ring_labels=False)
    palette = qv.Theme.light().palette
    for i in range(n):
        th0 = 2.0 * np.pi * i / n
        th1 = th0 + 2.0 * np.pi / n * 0.9
        color = palette[i % len(palette.colors)]
        node = node * qv.Polygon(wedge(th0, th1, 0.0, float(heights[i])),
                                 color=color, fill=True, alpha=0.6)
    return _frame(node, 10.0, "polar_bar (wedges via Polygon)")


def make_radar():
    """A radar / spider chart: two series over 5 axes."""
    cats = ["speed", "power", "range", "cost", "size"]
    a = np.array([4.0, 3.0, 5.0, 2.0, 4.0])
    b = np.array([2.0, 5.0, 3.0, 4.0, 3.0])
    n = len(cats)
    th = np.array([2.0 * np.pi * i / n for i in range(n)])
    node = polar_grid(5.0, rings=5, spokes=n, ring_labels=False,
                      spoke_labels=False)  # category names label the spokes
    palette = qv.Theme.light().palette
    for i, (series, label) in enumerate(((a, "unit A"), (b, "unit B"))):
        pts = [(float(r * np.cos(t)), float(r * np.sin(t)))
               for r, t in zip(series, th)]
        node = node * qv.Polygon(pts, fill=True, alpha=0.35, label=label,
                                 color=palette[i])
    for c, t in zip(cats, th):
        node = node * qv.Text(float(5.6 * np.cos(t)), float(5.6 * np.sin(t)),
                              c, halign="center")
    return _frame(node, 5.0, "radar (two series)")


# ── render on all three backends ─────────────────────────────────────────────
def main() -> int:
    import os

    from PySide6.QtWidgets import QApplication

    out = os.path.dirname(os.path.abspath(__file__))
    app = QApplication.instance() or QApplication(sys.argv)
    figures = {"polar_demo": make_polar_demo(), "polar_bar": make_polar_bar(),
               "radar": make_radar()}
    import qtviz.backends as B

    for backend_name in ("pyqtgraph", "matplotlib", "webengine"):
        if backend_name not in B.list_available():
            print(f"-- {backend_name}: unavailable, skipped")
            continue
        backend = B.get(backend_name)
        for name, node in figures.items():
            try:
                handle = backend.render(node, theme=qv.Theme.light())
                handle.widget.resize(640, 640)
                if backend_name == "webengine":  # page needs to paint first
                    handle.widget.show()
                    from PySide6.QtCore import QDeadlineTimer, QEventLoop
                    loop_until = QDeadlineTimer(2500)
                    while not loop_until.hasExpired():
                        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
                path = os.path.join(out, f"{name}_{backend_name}.png")
                handle.export("png", path)
                handle.dispose()
                print(f"ok {name} on {backend_name}: {path}")
            except Exception as e:  # noqa: BLE001 — spike: report, don't die
                print(f"XX {name} on {backend_name}: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
