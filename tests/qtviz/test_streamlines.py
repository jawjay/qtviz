"""Wave 1.5 — [D118] `Streamlines`: the last member of the 2-D field quartet.

mpl's streamplot algorithm reimplemented small, in core: seed on a coarse
mask grid (`30×30 · density`), integrate RK4 both directions with bilinear
field interpolation, terminate on domain exit / stagnation / an occupied
mask cell (the mask enforces line spacing). Output is polylines + one
mid-line arrowhead each (the [D107] head construction) — primitives every
backend already draws as two NaN-separated curves. Pure numpy,
property-tested. Scope cuts recorded in the element docstring: no
`color_by=speed` gradient, no varying width, no start-point control in v1.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_BOUNDS = (-2.0, -1.0, 2.0, 1.0)
_gy, _gx = np.mgrid[-1:1:25j, -2:2:41j]
_SWIRL_U = -_gy
_SWIRL_V = _gx


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS)
    qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS, density=2.0)
    # grid-contract violations surface at geometry time ([D129]: accessors
    # may be opaque callables, so the shape check runs on the resolved arrays)
    with pytest.raises(ValidationError):
        qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V[:, :-1]},
                       extent=_BOUNDS).resolved_paths()  # shape mismatch
    with pytest.raises(ValidationError):
        qv.Streamlines({"u": _SWIRL_U.ravel(), "v": _SWIRL_V.ravel()},
                       extent=_BOUNDS).resolved_paths()  # 1-D
    with pytest.raises(ValidationError):
        qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS, density=0.0)
    with pytest.raises(ValidationError):
        qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS, density=50.0)


# ── core integrator properties ───────────────────────────────────────────────
@pytest.mark.tier1
def test_uniform_field_gives_straight_lines():
    from qtviz.core._streamlines import streamline_paths

    u, v = np.ones((20, 30)), np.zeros((20, 30))
    paths, heads = streamline_paths(u, v, _BOUNDS)
    assert paths, "a uniform field must produce lines"
    for pts in paths:
        assert np.ptp(pts[:, 1]) < 1e-9          # horizontal: y constant
        assert np.all(np.diff(pts[:, 0]) > 0)    # monotone along the flow
    assert len(heads) == len(paths)              # one arrowhead per line


@pytest.mark.tier1
def test_lines_stay_inside_bounds():
    from qtviz.core._streamlines import streamline_paths

    paths, heads = streamline_paths(_SWIRL_U, _SWIRL_V, _BOUNDS)
    x0, y0, x1, y1 = _BOUNDS
    eps = 1e-9
    assert paths
    for pts in paths:
        assert pts[:, 0].min() >= x0 - eps and pts[:, 0].max() <= x1 + eps
        assert pts[:, 1].min() >= y0 - eps and pts[:, 1].max() <= y1 + eps
    for h in heads:
        assert h.shape == (3, 2)                 # left barb, tip, right barb


@pytest.mark.tier1
def test_mask_enforces_spacing():
    """No two lines claim the same spacing-mask cell — the mpl invariant."""
    from qtviz.core._streamlines import _mask_cells, streamline_paths

    paths, _ = streamline_paths(_SWIRL_U, _SWIRL_V, _BOUNDS, density=1.0)
    assert len(paths) > 3
    cell_sets = [_mask_cells(pts, _SWIRL_U.shape, _BOUNDS, 1.0) for pts in paths]
    for i in range(len(cell_sets)):
        for j in range(i + 1, len(cell_sets)):
            assert not (cell_sets[i] & cell_sets[j])


@pytest.mark.tier1
def test_density_scales_line_count():
    from qtviz.core._streamlines import streamline_paths

    lo, _ = streamline_paths(_SWIRL_U, _SWIRL_V, _BOUNDS, density=0.5)
    hi, _ = streamline_paths(_SWIRL_U, _SWIRL_V, _BOUNDS, density=2.0)
    assert len(hi) > len(lo)


@pytest.mark.tier1
def test_stagnant_field_gives_no_lines():
    from qtviz.core._streamlines import streamline_paths

    paths, heads = streamline_paths(np.zeros((10, 10)), np.zeros((10, 10)), _BOUNDS)
    assert paths == [] and heads == []


@pytest.mark.tier1
def test_heads_sit_on_their_lines():
    from qtviz.core._streamlines import streamline_paths

    paths, heads = streamline_paths(_SWIRL_U, _SWIRL_V, _BOUNDS)
    for pts, h in zip(paths, heads, strict=True):
        tip = h[1]
        d = np.hypot(pts[:, 0] - tip[0], pts[:, 1] - tip[1])
        assert d.min() < 0.15                    # tip lies on (near) the path


@pytest.mark.tier1
def test_webengine_streamline_traces():
    from qtviz.backends.webengine import _figure

    el = qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS, label="flow")
    traces = _figure.build_figure(el, qv.Theme.light())["data"]
    assert len(traces) == 2                      # lines + heads
    lines, heads = traces
    assert lines["mode"] == "lines" and heads["mode"] == "lines"
    assert lines["showlegend"] is True and lines["name"] == "flow"
    assert np.isnan(np.asarray(lines["x"], dtype="float64")).any()  # NaN-gapped


@pytest.mark.tier2
def test_pg_two_polyline_items(qtbot):
    import pyqtgraph as pg

    el = qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS)
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    items = handle.native(el.id)
    assert len(items) == 2
    assert all(isinstance(it, pg.PlotCurveItem) for it in items)


@pytest.mark.tier2
def test_backends_draw_identical_lines(qtbot):
    """[D110] payoff: matplotlib and pyqtgraph plot the same polylines."""
    pytest.importorskip("matplotlib")
    el = qv.Streamlines({"u": _SWIRL_U, "v": _SWIRL_V}, extent=_BOUNDS)
    h1 = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    h2 = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    a = np.asarray(h1.native(el.id)[0].get_xdata(), dtype="float64")
    b, _ = h2.native(el.id)[0].getData()
    assert np.allclose(a[~np.isnan(a)], b[~np.isnan(b)])
