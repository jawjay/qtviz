"""Roadmap wave 3, increment 2 — `Quiver` ([D107]).

Vector fields from ONE core geometry ([D110]): shafts + ±25° barbs as two
NaN-separated polylines, so every backend draws the identical field with two
cheap primitives (deliberately not mpl's native `quiver` — one meaning).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_gy, _gx = np.mgrid[0:5, 0:5]
_T = {"x": _gx.ravel().astype(float), "y": _gy.ravel().astype(float),
      "u": np.cos(_gx.ravel() / 2.0), "v": np.sin(_gy.ravel() / 2.0)}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Quiver(_T, x="x", y="y", u="u", v="v", arrow_scale=0.5, head_scale=2.0)
    with pytest.raises(ValidationError):
        qv.Quiver(_T, x="x", y="y", u="u", v="v", arrow_scale="big")
    with pytest.raises(ValidationError):
        qv.Quiver(_T, x="x", y="y", u="u", v="v", arrow_scale=-1.0)
    with pytest.raises(ValidationError):
        qv.Quiver(_T, x="x", y="y", u="u", v="v", head_scale=0.0)


@pytest.mark.tier1
def test_core_geometry():
    from qtviz.core._geometry import quiver_scale, quiver_segments

    x, y = np.array([0.0, 1.0]), np.array([0.0, 0.0])
    u, v = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    (sx, sy), (hx, hy) = quiver_segments(x, y, u, v, scale=1.0)
    assert len(sx) == 2 * 3 and len(hx) == 2 * 4       # 3/4 points per arrow
    assert (sx[0], sx[1]) == (0.0, 1.0)                # shaft 0: (0,0)→(1,0)
    assert np.isnan(sx[2])
    assert (hx[1], hy[1]) == (1.0, 0.0)                # barbs meet at the tip
    assert hx[0] < 1.0 and hy[0] > 0.0                 # one barb behind, above
    assert hx[2] < 1.0 and hy[2] < 0.0                 # the other behind, below
    s = quiver_scale(_T["x"], _T["y"], _T["u"], _T["v"])
    assert 0.0 < s * float(np.hypot(_T["u"], _T["v"]).max()) <= 1.0  # fits a cell


@pytest.mark.tier2
def test_backends_draw_identical_fields(qtbot):
    """[D110] payoff: matplotlib and pyqtgraph plot the same polylines."""
    pytest.importorskip("matplotlib")
    el = qv.Quiver(_T, x="x", y="y", u="u", v="v")
    h1 = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    h2 = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    mpl_shafts = h1.native(el.id)[0]
    pg_shafts = h2.native(el.id)[0]
    a = np.asarray(mpl_shafts.get_xdata(), dtype="float64")
    b, _ = pg_shafts.getData()
    assert np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])


@pytest.mark.tier1
def test_webengine_quiver_traces():
    from qtviz.backends.webengine import _figure

    traces = _figure.build_figure(
        qv.Quiver(_T, x="x", y="y", u="u", v="v"), qv.Theme.light())["data"]
    assert len(traces) == 2
    assert all(t["mode"] == "lines" for t in traces)
    assert len(traces[0]["x"]) == 25 * 3               # shafts
    assert len(traces[1]["x"]) == 25 * 4               # barbs
