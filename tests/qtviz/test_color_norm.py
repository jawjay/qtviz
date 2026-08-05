"""0.4 increment 4 — color normalization ([D71], milestone-0.4 §5).

`Scatter(color_by=…, norm="log")` maps colors through log10. Legend
honesty ([D48]): a log-normed color↔value relation is non-linear, so the
emitted Legend is `linear=False` → an endpoints-only key on every backend,
never a gradient bar implying linear ticks.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.encoding import map_colors  # noqa: E402
from qtviz.core.palette import palettes  # noqa: E402
from qtviz.errors import QtvizWarning, ValidationError  # noqa: E402

_DATA = {"x": np.arange(4.0), "y": np.arange(4.0),
         "mag": np.array([1.0, 10.0, 100.0, 10_000.0])}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


# ── Tier-1: the mapping itself ───────────────────────────────────────────────
@pytest.mark.tier1
def test_log_norm_maps_decades_evenly():
    ramp = palettes.get("viridis")
    rgba, legend = map_colors(np.array([1.0, 100.0, 10_000.0]),
                              palette=ramp, continuous_palette=ramp, norm="log")
    assert np.allclose(rgba[0], ramp.at(0.0).rgba, atol=0.02)   # 10^0 → bottom
    assert np.allclose(rgba[1], ramp.at(0.5).rgba, atol=0.02)   # 10^2 → midpoint
    assert np.allclose(rgba[2], ramp.at(1.0).rgba, atol=0.02)   # 10^4 → top
    assert legend.linear is False                               # [D48]: endpoints only
    assert (legend.vmin, legend.vmax) == (1.0, 10_000.0)        # data space, not log10


@pytest.mark.tier1
def test_log_norm_nonpositive_warns():
    ramp = palettes.get("viridis")
    with pytest.warns(QtvizWarning, match="non-positive"):
        rgba, _ = map_colors(np.array([-1.0, 1.0, 10.0]),
                             palette=ramp, continuous_palette=ramp, norm="log")
    assert rgba.shape == (3, 4)                                 # renders regardless


@pytest.mark.tier1
def test_color_norm_validation():
    with pytest.raises(ValidationError):
        qv.Scatter(_DATA, x="x", y="y", color_by="mag", norm="sqrt")
    with pytest.raises(ValidationError):
        qv.Scatter(_DATA, x="x", y="y", norm="log")       # needs color_by
    with pytest.raises(ValidationError):
        qv.Scatter(_DATA, x="x", y="y", clim=(0, 1))      # clim needs color_by too
    with pytest.raises(ValidationError):
        qv.Scatter(_DATA, x="x", y="y", color_by="mag", clim=(2.0, 1.0))  # lo >= hi


# ── Tier-1: [D130] on Scatter — clim + Norm specs ride the color_by mapping ──
@pytest.mark.tier1
def test_scatter_accepts_full_norm_clim_surface():
    el = qv.Scatter(_DATA, x="x", y="y", color_by="mag",
                    norm=qv.Norm("power", gamma=0.5), clim=(1.0, 100.0))
    assert el.norm_kind == "power"
    assert (el.vmin, el.vmax) == (1.0, 100.0)


@pytest.mark.tier1
def test_clim_pins_the_mapping_bounds():
    ramp = palettes.get("viridis")
    values = np.array([0.0, 5.0, 10.0])
    rgba, legend = map_colors(values, palette=ramp, continuous_palette=ramp,
                              vmin=0.0, vmax=5.0)
    # 5.0 sits at the top of a (0, 5) clim; 10.0 clips there too
    assert np.allclose(rgba[1], ramp.at(1.0).rgba, atol=0.02)
    assert np.allclose(rgba[2], ramp.at(1.0).rgba, atol=0.02)
    assert (legend.vmin, legend.vmax) == (0.0, 5.0)


@pytest.mark.tier1
def test_norm_spec_maps_through_power_gamma():
    ramp = palettes.get("viridis")
    values = np.array([0.0, 0.25, 1.0])
    rgba, legend = map_colors(values, palette=ramp, continuous_palette=ramp,
                              norm=qv.Norm("power", gamma=0.5))
    assert np.allclose(rgba[1], ramp.at(0.5).rgba, atol=0.02)   # 0.25**0.5 = 0.5
    assert legend.linear is False                               # non-linear key


@pytest.mark.tier2
def test_pyqtgraph_scatter_clim_reaches_the_mapping(qtbot):
    """The renderer feeds element clim into map_colors — two elements differing
    only in clim color the same point differently."""
    from qtviz.backends.pyqtgraph._renderers import _color_mapping

    base = qv.Scatter(_DATA, x="x", y="y", color_by="mag")
    pinned = qv.Scatter(_DATA, x="x", y="y", color_by="mag", clim=(1.0, 10.0))
    theme = qv.Theme.light()

    rgba_base, _ = _color_mapping(*_mapping_args(base, theme))
    rgba_pin, _ = _color_mapping(*_mapping_args(pinned, theme))
    assert not np.allclose(rgba_base, rgba_pin)


def _mapping_args(el, theme):
    from qtviz.data import resolve_node

    resolved = resolve_node(el)
    return resolved, resolved.data, theme


# ── Tier-2: honest legends on the native backends ────────────────────────────
@pytest.mark.tier2
def test_pyqtgraph_log_norm_shows_endpoints_key_not_gradient(qtbot):
    el = qv.Scatter(_DATA, x="x", y="y", color_by="mag", norm="log")
    view = qv.View(el, backend="pyqtgraph")
    qtbot.addWidget(view)
    plot = view.handle.plots[0]
    assert getattr(plot, "_qtviz_cbar", None) is None           # no lying gradient
    labels = [lb.text for _s, lb in plot._qtviz_legend.items]
    assert labels == ["1e+04", "1"]                             # data-space endpoints


@pytest.mark.tier2
def test_matplotlib_log_norm_shows_endpoints_key(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    el = qv.Scatter(_DATA, x="x", y="y", color_by="mag", norm="log")
    view = qv.View(el, backend="matplotlib")
    qtbot.addWidget(view)
    ax = view.handle.axes[0]
    assert getattr(ax, "_qtviz_cbar", None) is None
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["1e+04", "1"]


# ── Tier-1: webengine maps through the norm (css list, no linear colorbar) ───
@pytest.mark.tier1
def test_webengine_log_norm_uses_mapped_colors_not_linear_colorbar():
    from qtviz.backends.webengine import _figure

    el = qv.Scatter(_DATA, x="x", y="y", color_by="mag", norm="log")
    fig = _figure.build_figure(el, qv.Theme.light())
    marker = fig["data"][0]["marker"]
    assert isinstance(marker["color"], list)                    # pre-mapped css
    assert "colorbar" not in marker                             # no linear-bar lie
