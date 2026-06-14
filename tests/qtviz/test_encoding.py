"""Color encoding — values → per-element colors + a Legend (Tier 1, pure)."""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.encoding import Legend, is_categorical, map_colors  # noqa: E402
from qtviz.core.palette import Palette  # noqa: E402

pytestmark = pytest.mark.tier1

CATS = Palette.from_hex(["#ff0000", "#00ff00", "#0000ff"])
RAMP = Palette.from_hex(["#000000", "#ffffff"], kind="continuous")


def test_is_categorical_by_dtype():
    assert is_categorical(np.array(["a", "b"]))
    assert is_categorical(np.array([True, False]))
    assert not is_categorical(np.array([1.0, 2.0]))
    assert not is_categorical(np.array([1, 2, 3]))


def test_categorical_maps_distinct_values_to_distinct_colors():
    vals = np.array(["a", "b", "a", "c"])
    rgba, legend = map_colors(vals, palette=CATS, title="cat")
    assert rgba.shape == (4, 4)
    # same category → same color; different category → different
    assert np.array_equal(rgba[0], rgba[2])
    assert not np.array_equal(rgba[0], rgba[1])
    assert legend.kind == "categorical"
    assert [label for label, _ in legend.entries] == ["a", "b", "c"]
    assert legend.title == "cat"


def test_categorical_color_matches_palette_order():
    rgba, legend = map_colors(np.array(["a", "b", "c"]), palette=CATS)
    # unique() sorts → a,b,c map to palette[0,1,2]
    np.testing.assert_allclose(rgba[0], CATS[0].rgba)
    np.testing.assert_allclose(rgba[1], CATS[1].rgba)
    np.testing.assert_allclose(rgba[2], CATS[2].rgba)


def test_continuous_normalizes_and_builds_colorbar():
    vals = np.array([0.0, 5.0, 10.0])
    rgba, legend = map_colors(vals, palette=CATS, continuous_palette=RAMP, title="z")
    assert rgba.shape == (3, 4)
    # black→white ramp: min value darker than max
    assert rgba[0].sum() < rgba[2].sum()
    assert legend.kind == "continuous"
    assert legend.vmin == 0.0 and legend.vmax == 10.0
    assert len(legend.ramp) == 5
    assert legend.title == "z"


def test_continuous_respects_explicit_bounds():
    vals = np.array([2.0, 4.0, 6.0])
    _, legend = map_colors(vals, palette=CATS, continuous_palette=RAMP, vmin=0.0, vmax=10.0)
    assert legend.vmin == 0.0 and legend.vmax == 10.0


def test_kind_override_forces_categorical_on_numbers():
    rgba, legend = map_colors(np.array([1, 2, 1]), palette=CATS, kind="categorical")
    assert legend.kind == "categorical"
    assert np.array_equal(rgba[0], rgba[2])  # both value 1 → same color


def test_constant_continuous_does_not_divide_by_zero():
    rgba, legend = map_colors(np.array([3.0, 3.0]), palette=CATS, continuous_palette=RAMP)
    assert rgba.shape == (2, 4) and np.isfinite(rgba).all()
    assert legend.vmin == 3.0 and legend.vmax == 3.0


def test_nan_continuous_is_finite():
    rgba, _ = map_colors(np.array([0.0, np.nan, 10.0]), palette=CATS, continuous_palette=RAMP)
    assert np.isfinite(rgba).all()


def test_legend_is_frozen():
    legend = Legend(kind="categorical")
    with pytest.raises(AttributeError):  # frozen dataclass
        legend.title = "x"
