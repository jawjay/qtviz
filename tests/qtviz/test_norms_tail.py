"""Wave 1.4 — [D114] the norm tail: `symlog` and `boundary`.

Two new branches in the [D105] normalize/denormalize pair: symlog is the
standard piecewise log (mpl's formula, one numpy expression each way, with
`linthresh=`); boundary bins values into `len(levels)-1` discrete colors
sampled evenly from the colormap (`np.searchsorted` forward, bin-midpoint
backward). Grids stay bit-identical across backends; colorbars keep the
[D48] honesty rules (mpl: discrete bar with level ticks; pg: endpoints key;
Plotly: hidden scale for non-linear).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_Z = np.linspace(1.0, 1000.0, 12).reshape(3, 4)
_S = np.array([[-500.0, -10.0, -0.5, 0.0], [0.25, 2.0, 50.0, 1000.0]])


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1: validation ───────────────────────────────────────────────────────
@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Image(_S, extent=(0, 0, 4, 2), norm="symlog")
    qv.Image(_S, extent=(0, 0, 4, 2), norm=qv.Norm("symlog", linthresh=0.1))
    qv.Image(_Z, extent=(0, 0, 4, 3),
             norm=qv.Norm("boundary", levels=[0.0, 10.0, 100.0, 1000.0]))
    # [D130]: the cross-field mistakes are now structurally impossible — the
    # parameters live inside Norm, and Norm validates itself.
    with pytest.raises(ValidationError):
        qv.Norm("symlog", linthresh=0.0)
    with pytest.raises(ValidationError):
        qv.Norm("linear", linthresh=0.5)                      # linthresh needs symlog
    with pytest.raises(ValidationError):
        qv.Norm("boundary")                                   # boundary needs levels
    with pytest.raises(ValidationError):
        qv.Norm("boundary", levels=[1.0])                     # too short
    with pytest.raises(ValidationError):
        qv.Norm("boundary", levels=[3.0, 1.0, 2.0])           # not ascending
    with pytest.raises(ValidationError):
        qv.Norm("linear", levels=[0.0, 1.0])                  # levels need boundary
    # the same spec guards every raster element (shared check_norm_clim)
    with pytest.raises(ValidationError):
        qv.Heatmap({"x": [0.0], "y": [0.0], "z": [1.0]}, x="x", y="y", z="z",
                   norm="nope")
    with pytest.raises(ValidationError):
        qv.Mesh(np.ones((1, 1)), x=[0, 1], y=[0, 1], norm="nope")


# ── tier 1: symlog core ──────────────────────────────────────────────────────
@pytest.mark.tier1
def test_symlog_roundtrip():
    from qtviz.core.encoding import denormalize, normalize_values

    normed, lo, hi = normalize_values(_S, norm="symlog", linthresh=1.0)
    assert (lo, hi) == (-500.0, 1000.0)
    assert normed.min() == 0.0 and normed.max() == 1.0
    for j in range(_S.shape[0]):
        for i in range(_S.shape[1]):
            back = denormalize(float(normed[j, i]), lo, hi, "symlog", linthresh=1.0)
            assert back == pytest.approx(_S[j, i], rel=1e-9, abs=1e-9)


@pytest.mark.tier1
def test_symlog_is_linear_inside_and_log_outside():
    from qtviz.core.encoding import normalize_values

    a = np.array([[-1.0, -0.5, 0.0, 0.5, 1.0]])
    normed, _, _ = normalize_values(a, norm="symlog", linthresh=1.0,
                                    vmin=-1.0, vmax=1.0)
    # inside ±linthresh the mapping is linear → evenly spaced, symmetric on 0.5
    assert np.allclose(normed, [[0.0, 0.25, 0.5, 0.75, 1.0]])
    big = np.array([[-1000.0, 0.0, 1000.0]])
    n2, _, _ = normalize_values(big, norm="symlog", linthresh=1.0,
                                vmin=-1000.0, vmax=1000.0)
    assert n2[0, 1] == pytest.approx(0.5)                     # symmetric span → center


# ── tier 1: boundary core ────────────────────────────────────────────────────
@pytest.mark.tier1
def test_boundary_bins_discretely():
    from qtviz.core.encoding import normalize_values

    levels = [0.0, 1.0, 2.0, 4.0]
    a = np.array([[0.2, 0.9, 1.5], [3.0, 4.0, np.nan]])
    normed, lo, hi = normalize_values(a, norm="boundary", levels=levels)
    assert (lo, hi) == (0.0, 4.0)
    finite = normed[np.isfinite(normed)]
    assert len(np.unique(finite)) == 3                        # 3 bins, 3 colors
    assert normed[0, 0] == normed[0, 1]                       # same bin
    assert normed[0, 2] != normed[0, 0]
    assert normed[1, 1] == normed[1, 0]                       # top edge → last bin
    assert np.isnan(normed[1, 2])                             # NaN preserved
    # bin colors sample the colormap evenly: centers of a 3-way split of [0,1]
    assert sorted(np.unique(finite)) == pytest.approx([1 / 6, 3 / 6, 5 / 6])


@pytest.mark.tier1
def test_boundary_denormalizes_to_bin_midpoints():
    from qtviz.core.encoding import denormalize

    levels = [0.0, 1.0, 2.0, 4.0]
    assert denormalize(1 / 6, 0.0, 4.0, "boundary", levels=levels) == pytest.approx(0.5)
    assert denormalize(3 / 6, 0.0, 4.0, "boundary", levels=levels) == pytest.approx(1.5)
    assert denormalize(5 / 6, 0.0, 4.0, "boundary", levels=levels) == pytest.approx(3.0)


@pytest.mark.tier1
def test_webengine_norm_tail_hides_the_scale():
    from qtviz.backends.webengine import _figure

    light = qv.Theme.light()
    sym = _figure.build_figure(
        qv.Image(_S, extent=(0, 0, 4, 2), norm="symlog"), light)["data"][0]
    assert sym["showscale"] is False                          # non-linear rule ([D48])
    assert float(np.nanmax(sym["z"])) == 1.0
    bnd = _figure.build_figure(
        qv.Image(_Z, extent=(0, 0, 4, 3),
                 norm=qv.Norm("boundary", levels=[0.0, 10.0, 100.0, 1000.0])),
        light)["data"][0]
    assert bnd["showscale"] is False
    assert len(np.unique(bnd["z"][np.isfinite(bnd["z"])])) == 3


# ── tier 2 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier2
@pytest.mark.parametrize("kwargs", [
    {"norm": qv.Norm("symlog", linthresh=0.5)},
    {"norm": qv.Norm("boundary", levels=[0.0, 10.0, 100.0, 1000.0])},
])
def test_backends_color_identically(kwargs, qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Image(_Z, extent=(0, 0, 4, 3), **kwargs)
    h1 = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    h2 = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    a = np.asarray(h1.native(el.id).get_array())
    b = np.asarray(h2.native(el.id).image)
    assert np.array_equal(a, b)


@pytest.mark.tier2
def test_mpl_boundary_colorbar_has_level_ticks(qtbot):
    pytest.importorskip("matplotlib")
    levels = [0.0, 10.0, 100.0, 1000.0]
    el = qv.Image(_Z, extent=(0, 0, 4, 3), norm=qv.Norm("boundary", levels=levels))
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    fig = handle.axes[0].figure
    assert len(fig.axes) == 2                                 # image + colorbar
    cbar_ax = fig.axes[1]
    labels = [t.get_text() for t in cbar_ax.get_yticklabels()]
    assert labels == ["0", "10", "100", "1000"]               # the levels, verbatim


@pytest.mark.tier2
def test_mpl_symlog_colorbar_denormalizes(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Image(_S, extent=(0, 0, 4, 2), norm="symlog",
                  clim=(-1000.0, 1000.0))
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    cbar_ax = handle.axes[0].figure.axes[1]
    label = cbar_ax.yaxis.get_major_formatter()(0.5, 0)
    assert float(label) == pytest.approx(0.0, abs=1e-9)       # symmetric center
