"""Wave 1.4 — [D116] ErrorBars limit arrows.

`ErrorBars(lo_limit=, hi_limit=)` take optional boolean columns; where true,
that side's cap is drawn as an arrowhead — "the true value lies beyond" (the
mpl lolims/uplims semantic). Heads come from the [D107] quiver construction
(an arrow from the datum to the bar end: same ±25° barbs, 30% head, in data
space), drawn as the same two-polyline primitive Quiver uses — no new
drawing capability on any backend. The native bar on a limited side is
zeroed; the arrow shaft replaces it.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": np.array([0.0, 1.0, 2.0]),
      "y": np.array([1.0, 2.0, 3.0]),
      "err": np.array([0.5, 0.4, 0.3]),
      "lo_lim": np.array([True, False, False]),
      "hi_lim": np.array([False, True, False])}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.ErrorBars(_T, x="x", y="y", err="err", lo_limit="lo_lim", hi_limit="hi_lim")
    qv.ErrorBars(_T, x="x", y="y", err="err", direction="x", lo_limit="lo_lim")
    with pytest.raises(ValidationError):  # per-axis semantics — no 'both'
        qv.ErrorBars(_T, x="x", y="y", err="err", direction="both",
                     lo_limit="lo_lim")


@pytest.mark.tier1
def test_core_limit_arrows_point_outward():
    from qtviz.core._geometry import limit_arrow_segments

    x, y = np.array([0.0, 1.0]), np.array([1.0, 2.0])
    lo, hi = np.array([0.5, 0.5]), np.array([0.4, 0.4])
    (sx, sy), (hx, hy) = limit_arrow_segments(
        x, y, lo, hi, np.array([True, False]), np.array([False, True]))
    assert len(sx) == 2 * 3                          # two arrows, 3 pts/shaft
    # arrow 1: down from (0, 1) to (0, 0.5) — the low cap, pointing beyond
    assert (sx[0], sy[0]) == (0.0, 1.0)
    assert (sx[1], sy[1]) == (0.0, 0.5)
    # arrow 2: up from (1, 2) to (1, 2.4)
    assert (sx[3], sy[3]) == (1.0, 2.0)
    assert (sx[4], sy[4]) == pytest.approx((1.0, 2.4))
    # barbs meet at the tips, behind the tip in the arrow direction
    assert (hx[1], hy[1]) == (0.0, 0.5)
    assert hy[0] > 0.5 and hy[2] > 0.5               # down arrow: barbs above tip
    assert (hx[5], hy[5]) == pytest.approx((1.0, 2.4))
    assert hy[4] < 2.4 and hy[6] < 2.4               # up arrow: barbs below tip


@pytest.mark.tier1
def test_core_limit_arrows_direction_x():
    from qtviz.core._geometry import limit_arrow_segments

    (sx, sy), (hx, hy) = limit_arrow_segments(
        np.array([1.0]), np.array([0.0]), np.array([0.5]), np.array([0.5]),
        np.array([True]), None, direction="x")
    assert (sx[0], sy[0]) == (1.0, 0.0)
    assert (sx[1], sy[1]) == (0.5, 0.0)              # low side of x
    assert np.all(np.isfinite(hy[:3]))


@pytest.mark.tier1
def test_core_no_limits_no_arrows():
    from qtviz.core._geometry import limit_arrow_segments

    (sx, _), (hx, _) = limit_arrow_segments(
        np.array([0.0]), np.array([1.0]), np.array([0.5]), np.array([0.5]),
        None, None)
    assert len(sx) == 0 and len(hx) == 0


@pytest.mark.tier1
def test_webengine_zeroes_limited_sides_and_adds_arrow_trace():
    from qtviz.backends.webengine import _figure

    el = qv.ErrorBars(_T, x="x", y="y", err="err",
                      lo_limit="lo_lim", hi_limit="hi_lim")
    traces = _figure.build_figure(el, qv.Theme.light())["data"]
    assert len(traces) == 2                          # bars + limit arrows
    bars, arrows = traces
    assert list(bars["error_y"]["arrayminus"]) == [0.0, 0.4, 0.3]  # lo zeroed at 0
    assert list(bars["error_y"]["array"]) == [0.5, 0.0, 0.3]       # hi zeroed at 1
    assert arrows["mode"] == "lines" and arrows["showlegend"] is False


@pytest.mark.tier2
def test_mpl_draws_limit_arrow_polylines(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.ErrorBars(_T, x="x", y="y", err="err",
                      lo_limit="lo_lim", hi_limit="hi_lim")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    native = handle.native(el.id)
    assert isinstance(native, list) and len(native) == 3   # bars, shafts, heads
    shafts = native[1]
    xs = np.asarray(shafts.get_xdata(), dtype="float64")
    assert np.sum(np.isnan(xs)) == 2                       # two arrows, NaN-gapped


@pytest.mark.tier2
def test_pg_draws_limit_arrow_polylines(qtbot):
    import pyqtgraph as pg

    el = qv.ErrorBars(_T, x="x", y="y", err="err",
                      lo_limit="lo_lim", hi_limit="hi_lim")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    native = handle.native(el.id)
    assert isinstance(native, list) and len(native) == 3
    assert isinstance(native[0], pg.ErrorBarItem)
    assert all(isinstance(it, pg.PlotCurveItem) for it in native[1:])


@pytest.mark.tier2
def test_plain_errorbars_unchanged(qtbot):
    """No limits → the single native artist, exactly as before [D116]."""
    el = qv.ErrorBars(_T, x="x", y="y", err="err")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    import pyqtgraph as pg

    assert isinstance(handle.native(el.id), pg.ErrorBarItem)
