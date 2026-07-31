"""Roadmap wave 2, increment 3 — raster color norms ([D105]).

`Image`/`Heatmap` gain `norm="linear"|"log"|"power"`, `vmin`/`vmax` and
`gamma` — normalized once in core so every backend colors identically.
Legends only appear when the norm surface is engaged (plain rasters keep
their exact pre-[D105] look): matplotlib draws a colorbar whose ticks are
denormalized back to data values; pyqtgraph reuses the legend machinery
(gradient bar for linear, endpoints-only for non-linear, [D48]); Plotly
keeps its native honest colorbar for linear and hides the scale otherwise.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_Z = np.linspace(1.0, 1000.0, 12).reshape(3, 4)


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Image(_Z, bounds=(0, 0, 4, 3), norm="log")
    qv.Image(_Z, bounds=(0, 0, 4, 3), norm="power", gamma=0.5)
    qv.Heatmap({"x": [0.0, 1.0], "y": [0.0, 0.0], "z": [1.0, 2.0]},
               x="x", y="y", z="z", vmin=0.0, vmax=5.0)
    with pytest.raises(ValidationError):
        qv.Image(_Z, bounds=(0, 0, 4, 3), norm="sqrt")
    with pytest.raises(ValidationError):
        qv.Image(_Z, bounds=(0, 0, 4, 3), gamma=0.5)          # gamma needs power
    with pytest.raises(ValidationError):
        qv.Image(_Z, bounds=(0, 0, 4, 3), vmin=5.0, vmax=1.0)
    with pytest.raises(ValidationError):
        qv.Image(_Z, bounds=(0, 0, 4, 3), norm="log", vmin=-1.0)


@pytest.mark.tier1
def test_core_normalize_roundtrip():
    from qtviz.core.encoding import denormalize, normalize_values

    normed, lo, hi = normalize_values(_Z, norm="log")
    assert (lo, hi) == (1.0, 1000.0)
    assert normed.min() == 0.0 and normed.max() == 1.0
    mid = denormalize(0.5, lo, hi, "log")
    assert mid == pytest.approx(10.0 ** 1.5)                  # geometric midpoint
    p, lo2, hi2 = normalize_values(_Z, norm="power", gamma=0.5)
    assert denormalize(p[1, 1], lo2, hi2, "power", 0.5) == pytest.approx(_Z[1, 1])


@pytest.mark.tier1
def test_core_log_nonpositive_blank():
    from qtviz.core.encoding import normalize_values
    from qtviz.errors import QtvizWarning

    with pytest.warns(QtvizWarning, match="non-positive"):
        normed, _, _ = normalize_values(np.array([[0.0, 1.0], [10.0, 100.0]]),
                                        norm="log")
    assert np.isnan(normed[0, 0])


@pytest.mark.tier1
def test_webengine_norms():
    from qtviz.backends.webengine import _figure

    light = qv.Theme.light()
    lin = _figure.build_figure(
        qv.Image(_Z, bounds=(0, 0, 4, 3), vmin=100.0, vmax=500.0), light)["data"][0]
    assert (lin["zmin"], lin["zmax"]) == (100.0, 500.0)       # raw z, honest bar
    assert "showscale" not in lin
    logt = _figure.build_figure(
        qv.Image(_Z, bounds=(0, 0, 4, 3), norm="log"), light)["data"][0]
    assert logt["showscale"] is False                         # no lying colorbar
    assert (logt["zmin"], logt["zmax"]) == (0.0, 1.0)
    assert float(np.nanmax(logt["z"])) == 1.0


# ── tier 2 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_log_norm_colorbar_denormalized(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Image(_Z, bounds=(0, 0, 4, 3), norm="log")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    fig = handle.axes[0].figure
    assert len(fig.axes) == 2                                 # image + colorbar
    artist = handle.native(el.id)
    assert float(np.nanmax(artist.get_array())) == 1.0        # core-normalized
    cbar_ax = fig.axes[1]
    label = cbar_ax.yaxis.get_major_formatter()(0.5, 0)
    assert float(label) == pytest.approx(10.0 ** 1.5, rel=1e-3)


@pytest.mark.tier2
def test_mpl_plain_raster_unchanged(qtbot):
    """No engaged norm → no colorbar, raw values (the pre-[D105] look)."""
    pytest.importorskip("matplotlib")
    el = qv.Image(_Z, bounds=(0, 0, 4, 3))
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert len(handle.axes[0].figure.axes) == 1
    assert float(np.nanmax(handle.native(el.id).get_array())) == 1000.0


@pytest.mark.tier2
def test_pg_norm_levels_and_endpoint_legend(qtbot):
    el = qv.Image(_Z, bounds=(0, 0, 4, 3), norm="log")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert tuple(item.getLevels()) == (0.0, 1.0)
    assert float(np.nanmax(item.image)) == 1.0


@pytest.mark.tier2
def test_backends_color_identically(qtbot):
    """[D110] payoff: the normalized grids matplotlib and pyqtgraph draw are
    bit-identical (one core normalization)."""
    pytest.importorskip("matplotlib")
    el = qv.Image(_Z, bounds=(0, 0, 4, 3), norm="power", gamma=0.4)
    h1 = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    h2 = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    a = np.asarray(h1.native(el.id).get_array())
    b = np.asarray(h2.native(el.id).image)
    assert np.array_equal(a, b)
