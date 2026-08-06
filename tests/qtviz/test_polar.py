"""[D119] polar wave — Option B per design/spikes/polar-spike-report.md.

Polar is a *transform*, not a projection: `qv.polar()` rebinds a tabular
element's x/y through (θ, r) → (r·cosθ, r·sinθ) before the data seam,
`qv.PolarGrid` draws the circular chrome from marks (one `lower()`, zero
backend edits), and `qv.wedge()` builds annulus-sector points for
`Polygon` polar bars. The surface stays rectilinear (`aspect=1`), so R1,
events, brushes, state, and backend switching are untouched by design.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.lowering import LowerContext  # noqa: E402
from qtviz.core.marks import PolygonMark, Polyline, TextMark  # noqa: E402
from qtviz.errors import ValidationError  # noqa: E402

_D = {"t": [0.0, np.pi / 2.0, np.pi], "r": [1.0, 2.0, 3.0]}


def _ctx():
    return LowerContext(theme=qv.Theme.light(), series_index=0, show_legend=True)


# ── PolarGrid: the chrome element ────────────────────────────────────────────
@pytest.mark.tier1
def test_polar_grid_validation():
    ok = qv.PolarGrid(5.0, rings=3, spokes=6)
    assert ok.r_max == 5.0 and ok.rings == 3 and ok.spokes == 6
    with pytest.raises(ValidationError):
        qv.PolarGrid(0.0)                       # r_max must be positive
    with pytest.raises(ValidationError):
        qv.PolarGrid(1.0, rings=0)
    with pytest.raises(ValidationError):
        qv.PolarGrid(1.0, spokes=1)
    with pytest.raises(ValidationError):        # custom labels must match spokes
        qv.PolarGrid(1.0, spokes=4, theta_labels=("a", "b"))


@pytest.mark.tier1
def test_polar_grid_value_identity():
    a = qv.PolarGrid(2.0, rings=4, spokes=8)
    assert a == qv.PolarGrid(2.0, rings=4, spokes=8)
    assert a != qv.PolarGrid(2.0, rings=5, spokes=8)
    assert a != qv.PolarGrid(2.0, rings=4, spokes=8, theta_labels=False)


@pytest.mark.tier1
def test_polar_grid_lowers_to_marks():
    """Rings = ONE NaN-separated PolygonMark, spokes = ONE pair-connected
    Polyline, labels = TextMarks (8 degree labels + 4 ring labels)."""
    lowered = qv.PolarGrid(2.0, rings=4, spokes=8).lower(_ctx())
    polys = [m for m in lowered.marks if isinstance(m, PolygonMark)]
    lines = [m for m in lowered.marks if isinstance(m, Polyline)]
    texts = [m for m in lowered.marks if isinstance(m, TextMark)]
    assert len(polys) == 1 and len(lines) == 1
    assert lines[0].connect == "pairs" and len(lines[0].x) == 16  # 8 spokes × 2
    assert len(texts) == 12
    assert lowered.legend is None               # chrome — no legend entry
    # custom spoke labels (the radar case) replace the degree texts
    radar = qv.PolarGrid(2.0, rings=4, spokes=3, r_labels=False,
                         theta_labels=("a", "b", "c")).lower(_ctx())
    labels = [m.text for m in radar.marks if isinstance(m, TextMark)]
    assert labels == ["a", "b", "c"]
    # switches drop their marks
    bare = qv.PolarGrid(2.0, theta_labels=False, r_labels=False).lower(_ctx())
    assert not [m for m in bare.marks if isinstance(m, TextMark)]


# ── polar(): the transform ───────────────────────────────────────────────────
@pytest.mark.tier1
def test_polar_transform_rebinds_xy():
    """x=θ, y=r reinterpreted: known angles land on the axes."""
    from qtviz.data import resolve_node

    el = qv.polar(qv.Curve(_D, x="t", y="r"))
    resolved = resolve_node(el)
    x = resolved.data.series("x")
    y = resolved.data.series("y")
    assert x == pytest.approx([1.0, 0.0, -3.0], abs=1e-12)
    assert y == pytest.approx([0.0, 2.0, 0.0], abs=1e-12)


@pytest.mark.tier1
def test_polar_explicit_accessors_and_serializable_expr():
    """Explicit theta=/r= win; str/col() arms compose into a serializable
    Expression (the [D14] preferred derived form — lazy-capable)."""
    from qtviz.data.expr import Expr

    el = qv.polar(qv.Scatter(_D, x="t", y="r"), theta=qv.col("t"), r="r")
    assert isinstance(el.x, Expr) and isinstance(el.y, Expr)
    assert el.x.columns() == {"t", "r"}
    # value identity survives (Expr arms are value-equal)
    el2 = qv.polar(qv.Scatter(_D, x="t", y="r"), theta=qv.col("t"), r="r")
    assert el.x == el2.x


@pytest.mark.tier1
def test_polar_callable_arm():
    el = qv.polar(qv.Curve(_D, x="t", y="r"), theta=lambda d: np.asarray(d["t"]))
    from qtviz.data import resolve_node

    x = resolve_node(el).data.series("x")
    assert x == pytest.approx([1.0, 0.0, -3.0], abs=1e-12)


@pytest.mark.tier1
def test_polar_rejects_non_tabular():
    with pytest.raises(ValidationError):
        qv.polar(qv.Heatmap(_D | {"z": [1.0, 2.0, 3.0]}, x="t", y="r", z="z"))
    with pytest.raises(ValidationError):
        qv.polar(qv.PolarGrid(1.0))             # chrome binds no data


# ── wedge(): polar-bar geometry ──────────────────────────────────────────────
@pytest.mark.tier1
def test_wedge_points():
    pts = qv.wedge(0.0, np.pi / 2.0, 1.0, 2.0, steps=3)
    assert len(pts) == 6                        # 3 outer + 3 inner
    assert pts[0] == pytest.approx((2.0, 0.0))  # outer arc starts at θ0·r1
    assert pts[2] == pytest.approx((0.0, 2.0), abs=1e-12)
    assert pts[-1] == pytest.approx((1.0, 0.0))  # inner arc ends at θ0·r0
    qv.Polygon(qv.wedge(0.0, 1.0, 0.0, 1.0))    # feeds Polygon directly
    with pytest.raises(ValidationError):
        qv.wedge(0.0, 1.0, 2.0, 1.0)            # r1 must exceed r0


# ── renders on every backend (the [D122] promise: zero backend edits) ────────
def _node():
    r = np.linspace(0.0, 2.0, 30)
    theta = 2.0 * np.pi * r
    spiral = qv.polar(qv.Curve({"t": theta, "r": r}, x="t", y="r"))
    return (qv.PolarGrid(2.0) * spiral).opts(
        aspect=1.0, grid=False,
        x=qv.AxisSpec(lim=(-2.6, 2.6), ticks=()),
        y=qv.AxisSpec(lim=(-2.6, 2.6), ticks=()))


@pytest.mark.tier2
@pytest.mark.parametrize("name", ["pyqtgraph", "matplotlib"])
def test_renders_on_native_backends(name, qtbot):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} unavailable")
    handle = B.get(name).render(_node(), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    handle.dispose()


@pytest.mark.tier1
def test_webengine_figure_builds():
    pytest.importorskip("plotly")
    from qtviz.backends.webengine._figure import build_figure

    fig = build_figure(_node(), qv.Theme.light())
    assert fig["data"]                          # the spiral trace landed
    assert fig["layout"].get("shapes") or fig["layout"].get("annotations")
