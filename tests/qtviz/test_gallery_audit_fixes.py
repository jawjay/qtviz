"""Fixes for the defects the matplotlib-gallery audit surfaced
(design/matplotlib-gallery-audit.md §2).

P1: the [D95] rubber-band selector parked a 0×0 rectangle at (0,0) on every
brushable matplotlib surface, and the artist joined `Axes.dataLim` — so
autoscale dragged every far-from-origin plot (all epoch-seconds time axes)
out to 1970. Plus: `Histogram` gains `alpha=` like every other filled
element, and matplotlib colormap names resolve case-insensitively with the
same warn-fallback contract as the other backends.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_EPOCH0 = 1_767_225_600.0  # 2026-01-01T00:00Z


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── P1: selector must not corrupt autoscale ──────────────────────────────────
@pytest.mark.tier2
def test_mpl_brush_selector_does_not_pollute_datalim(qtbot):
    """A 2026 time series must autoscale to 2026 — not to [1970, 2026]."""
    pytest.importorskip("matplotlib")
    days = np.arange("2026-01-01", "2026-03-01",
                     dtype="datetime64[D]").astype("datetime64[ns]")
    el = qv.Curve({"d": days, "v": np.arange(len(days), dtype=float)},
                  x="d", y="v")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert ax._qtviz_brush is not None          # the brush is still wired
    x0, x1 = ax.dataLim.intervalx
    assert x0 >= _EPOCH0 - 86400                # dataLim excludes the origin
    ax.figure.canvas.draw()
    lo, hi = ax.get_xlim()
    assert lo >= _EPOCH0 - 30 * 86400           # autoscale stays near the data


@pytest.mark.tier2
def test_mpl_brush_selector_datalim_clean_for_scatter(qtbot):
    """Collections too (relim() would have dropped them — the fix must not)."""
    pytest.importorskip("matplotlib")
    el = qv.Scatter({"x": [100.0, 110.0], "y": [200.0, 210.0]}, x="x", y="y")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    x0, x1 = ax.dataLim.intervalx
    assert (x0, x1) == (100.0, 110.0)           # scatter extent, no (0,0)
    y0, y1 = ax.dataLim.intervaly
    assert (y0, y1) == (200.0, 210.0)


# ── Histogram alpha ──────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_histogram_alpha_validates():
    from qtviz.errors import ValidationError

    qv.Histogram({"v": [1.0, 2.0]}, value="v", alpha=0.5)
    with pytest.raises(ValidationError):
        qv.Histogram({"v": [1.0, 2.0]}, value="v", alpha=1.5)


@pytest.mark.tier2
def test_mpl_histogram_honors_alpha(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Histogram({"v": list(np.random.default_rng(0).normal(0, 1, 100))},
                      value="v", alpha=0.4)
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.axes[0].patches[0].get_alpha() == 0.4


@pytest.mark.tier2
def test_pg_histogram_honors_alpha(qtbot):
    el = qv.Histogram({"v": list(np.random.default_rng(0).normal(0, 1, 100))},
                      value="v", alpha=0.4)
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    opts = handle.native(el.id).opts
    brush = opts.get("brushes") or opts.get("brush")
    assert brush.color().alphaF() == pytest.approx(0.4, abs=0.01)


@pytest.mark.tier1
def test_webengine_histogram_honors_alpha():
    from qtviz.backends.webengine import _figure

    el = qv.Histogram({"v": [1.0, 2.0, 2.0, 3.0]}, value="v", alpha=0.4)
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["opacity"] == 0.4


# ── colormap case-insensitivity on matplotlib ────────────────────────────────
@pytest.mark.tier2
def test_mpl_colormap_case_insensitive(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Image(np.arange(12.0).reshape(3, 4), bounds=(0, 0, 4, 3),
                  colormap="greys")  # mpl registry name is "Greys"
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id).get_cmap().name == "Greys"


@pytest.mark.tier2
def test_mpl_unknown_colormap_warns_and_falls_back(qtbot):
    pytest.importorskip("matplotlib")
    from qtviz.errors import QtvizWarning

    el = qv.Heatmap({"x": [0.0, 1.0], "y": [0.0, 0.0], "z": [1.0, 2.0]},
                    x="x", y="y", z="z", colormap="not_a_real_map")
    with pytest.warns(QtvizWarning, match="colormap"):
        handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id).get_cmap().name == "viridis"
