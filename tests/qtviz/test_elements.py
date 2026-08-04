"""Tier-1 — Element construction & validation (spec §5, §2.11, §6.1).

Elements are pure data with eager, actionable validation: mutually-exclusive
visual/column pairs, range checks, and schema-validated field names (a typo'd
column raises at construction, not at render — §2.1/§6.1).
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1


def test_curated_vocabulary_constructs(make_elements):
    elements = make_elements(qv)
    assert set(elements) == {
        # the 8 Phase-1 data elements
        "Scatter", "Curve", "Bars", "Histogram",
        "ErrorBars", "Spread", "Image", "Heatmap",
        # the 0.4 annotation/reference elements ([D70])
        "HLine", "VLine", "Span", "Text",
        # the 0.4 statistical elements ([D67])
        "BoxPlot", "Violin",
        # the parity-increment-3 composition vocabulary ([D84b]/[D90]/[D91])
        "Area", "Ecdf", "Pie", "Contour", "Mesh", "Quiver",
        # wave-1 annotations ([D96]/[D97]/[D99])
        "Arrow", "Rect", "Ellipse", "Polygon", "RefLine",
        # waves 1.4/1.5 ([D115]/[D118])
        "Stem", "Streamlines",
    }


def test_scatter_required_options():
    assert qv.Scatter.REQUIRED_OPTIONS == ("x", "y")


def test_color_and_color_by_mutually_exclusive(table):
    with pytest.raises(ValueError):
        qv.Scatter(table, x="x", y="y", color="red", color_by="cat")


def test_size_and_size_by_mutually_exclusive(table):
    with pytest.raises(ValueError):
        qv.Scatter(table, x="x", y="y", size=5.0, size_by="z")


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_alpha_out_of_range_rejected(table, bad):
    with pytest.raises(ValueError):
        qv.Scatter(table, x="x", y="y", alpha=bad)


def test_unknown_field_name_rejected_at_construction(table):
    with pytest.raises((ValueError, KeyError)):
        qv.Scatter(table, x="tmie", y="y")  # typo'd column


def test_raster_defaults_to_native(table):
    assert qv.Scatter(table, x="x", y="y").raster == "native"


def test_elements_are_immutable(make_elements):
    for el in make_elements(qv).values():
        with pytest.raises(AttributeError):
            el.id = "mutated"  # type: ignore[misc]


def test_image_requires_gridded_data(table):
    # Image needs an array grid; a tabular dict has no 2-D values → clear error.
    with pytest.raises((ValueError, TypeError)):
        qv.Image(table, extent=(0, 0, 1, 1))
