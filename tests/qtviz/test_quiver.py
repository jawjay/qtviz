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


# ── [D112] reference key — a truthful legend entry, not axes-fraction chrome ──
@pytest.mark.tier1
def test_key_validation():
    from qtviz.errors import ValidationError

    qv.Quiver(_T, x="x", y="y", u="u", v="v", key=10.0, key_label="10 m/s")
    with pytest.raises(ValidationError):
        qv.Quiver(_T, x="x", y="y", u="u", v="v", key=0.0)
    with pytest.raises(ValidationError):
        qv.Quiver(_T, x="x", y="y", u="u", v="v", key=-2.0)
    with pytest.raises(ValidationError):  # a label for a key that doesn't exist
        qv.Quiver(_T, x="x", y="y", u="u", v="v", key_label="10 m/s")


@pytest.mark.tier1
def test_key_sample_geometry_matches_field_construction():
    """The legend sample is built by the same [D107] construction as the field
    arrows (±25° barbs, 30% head × head_scale) — truthful by construction."""
    from qtviz.core._geometry import arrow_key_points

    shaft, head = arrow_key_points()
    assert shaft.shape == (2, 2) and head.shape == (3, 2)
    assert np.allclose(shaft, [[0.0, 0.0], [1.0, 0.0]])   # unit arrow along +x
    assert np.allclose(head[1], [1.0, 0.0])               # barbs meet at the tip
    assert head[0][0] < 1.0 and head[0][1] > 0.0
    assert head[2][0] < 1.0 and head[2][1] < 0.0
    _, head2 = arrow_key_points(head_scale=2.0)
    barb = np.hypot(*(head[1] - head[0]))
    barb2 = np.hypot(*(head2[1] - head2[0]))
    assert np.isclose(barb2, 2.0 * barb)                  # head_scale honored


@pytest.mark.tier1
def test_key_legend_entry():
    theme = qv.Theme.light()
    base = {"x": "x", "y": "y", "u": "u", "v": "v"}
    e = qv.Quiver(_T, **base, key=10.0).legend_entry(theme)
    assert e.glyph == "arrow" and e.label == "10"
    e2 = qv.Quiver(_T, **base, key=10.0, key_label="10 m/s").legend_entry(theme)
    assert e2.label == "10 m/s"
    e3 = qv.Quiver(_T, **base, label="wind", key=10.0,
                   key_label="10 m/s").legend_entry(theme)
    assert e3.label == "wind (10 m/s)" and e3.glyph == "arrow"
    e4 = qv.Quiver(_T, **base, label="wind").legend_entry(theme)
    assert e4.glyph == "swatch" and e4.label == "wind"    # no key → plain entry
    assert qv.Quiver(_T, **base).legend_entry(theme) is None
    e5 = qv.Quiver(_T, **base, key=10.0, head_scale=2.0).legend_entry(theme)
    assert e5.head_scale == 2.0                           # sample matches field


@pytest.mark.tier1
def test_webengine_key_is_a_legend_only_trace():
    from qtviz.backends.webengine import _figure

    traces = _figure.build_figure(
        qv.Quiver(_T, x="x", y="y", u="u", v="v", key=10.0, key_label="10 m/s"),
        qv.Theme.light())["data"]
    assert len(traces) == 3
    key = traces[-1]
    assert key["showlegend"] is True and key["name"] == "10 m/s"
    assert key["x"] == [None] and key["y"] == [None]      # draws nothing on-plot


@pytest.mark.tier2
def test_pg_key_lands_in_the_legend(qtbot):
    el = qv.Quiver(_T, x="x", y="y", u="u", v="v", key=10.0, key_label="10 m/s")
    view = qv.View(qv.Overlay((el,)), backend="pyqtgraph")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    lg = getattr(view.handle.plots[0], "_qtviz_legend", None)
    assert lg is not None
    labels = [label.text for _sample, label in lg.items]
    assert "10 m/s" in labels


@pytest.mark.tier2
def test_mpl_key_lands_in_the_legend(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Quiver(_T, x="x", y="y", u="u", v="v", key=10.0, key_label="10 m/s")
    view = qv.View(qv.Overlay((el,)), backend="matplotlib")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    legend = view.handle.axes[0].get_legend()
    assert legend is not None
    assert "10 m/s" in [t.get_text() for t in legend.get_texts()]
