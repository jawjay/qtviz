"""Tier-1 — the Mark IR foundation ([D121]/[D122]/[D123], wave 0).

Covers the mark vocabulary (frozen, coerced, structurally comparable), the
Element lowering hooks (default = does-not-lower), and the pilot
`Quiver.lower()` — including the golden parity check (marks carry exactly the
[D107] `resolved_segments()` geometry) and a Quiver-scoped preview of the
[D123] perturbation guard: every `HONORED_BY_LOWERING` option must visibly
change the `Lowered`, and identity fields must not.

Nothing here touches the render path: backends still dispatch through their
registries until wave 2.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.lowering import LowerContext, Lowered, resolve_color  # noqa: E402
from qtviz.core.marks import (  # noqa: E402
    MARK_TYPES,
    Fill,
    Polyline,
    Rects,
    Rule,
    Stroke,
    TextMark,
    structurally_equal,
)

pytestmark = pytest.mark.tier1

THEME = qv.Theme.light()
CTX = LowerContext(theme=THEME)


def _stroke(**kw) -> Stroke:
    return Stroke(qv.Color("red"), **kw)


# ---------------------------------------------------------------- vocabulary


def test_marks_are_frozen_dataclasses():
    for mark_type in MARK_TYPES:
        assert dataclasses.is_dataclass(mark_type)
        assert mark_type.__dataclass_params__.frozen


def test_polyline_coerces_to_float64_and_is_frozen():
    p = Polyline([0, 1, 2], [0.0, np.nan, 2.0], _stroke())
    assert p.x.dtype == np.float64 and p.y.dtype == np.float64
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.connect = "pairs"  # type: ignore[misc]


def test_array_marks_do_not_pretend_to_be_value_hashable():
    a = Polyline([0, 1], [0, 1], _stroke())
    b = Polyline([0, 1], [0, 1], _stroke())
    assert a != b  # eq=False: identity semantics, never array-based __eq__
    assert structurally_equal(a, b)


def test_structurally_equal_is_nan_aware():
    a = Polyline([0, np.nan], [1, 2], _stroke())
    b = Polyline([0, np.nan], [1, 2], _stroke())
    assert structurally_equal(a, b)


def test_structurally_equal_sees_array_and_style_differences():
    base = Polyline([0, 1], [0, 1], _stroke())
    assert not structurally_equal(base, Polyline([0, 2], [0, 1], _stroke()))
    assert not structurally_equal(base, Polyline([0, 1], [0, 1], _stroke(width=3.0)))
    assert not structurally_equal(base, Rule("h", _stroke()))  # type mismatch


def test_structurally_equal_recurses_nested_mark_tuples():
    label = TextMark(0.5, 1.0, "3", qv.Color("black"))
    a = Rects([0], [1], [0], [1], fill=Fill(qv.Color("blue")), labels=(label,))
    b = Rects([0], [1], [0], [1], fill=Fill(qv.Color("blue")), labels=(label,))
    assert structurally_equal(a, b)
    c = Rects([0], [1], [0], [1], fill=Fill(qv.Color("blue")),
              labels=(TextMark(0.5, 1.0, "4", qv.Color("black")),))
    assert not structurally_equal(a, c)


def test_resolve_color_explicit_wins_else_palette_slot():
    assert resolve_color("red", THEME) == qv.Color("red")
    assert resolve_color(None, THEME, 1) == THEME.palette[1]
    n = len(THEME.palette)
    assert resolve_color(None, THEME, n) == THEME.palette[0]  # wraps


# ---------------------------------------------------------- element hooks


def test_element_default_does_not_lower(table):
    s = qv.Scatter(table, x="x", y="y")
    assert s.lower(CTX) is None
    assert type(s).lower is qv.Scatter.__mro__[1].lower  # base impl → native-only
    assert s.select_xy() is None
    assert frozenset() == s.HONORED_BY_LOWERING


def test_data_kind_metadata():
    assert qv.Scatter.DATA_KIND == "tabular"
    assert qv.Histogram.DATA_KIND == "tabular"
    for gridded in (qv.Image, qv.Contour, qv.Mesh):
        assert gridded.DATA_KIND == "gridded"
    for data_less in (qv.HLine, qv.Text, qv.Rect, qv.RawFigure, qv.Streamlines):
        assert data_less.DATA_KIND == "none"


def test_data_less_elements_resolve_data_without_getattr():
    h = qv.HLine(1.0)
    assert h.data is None  # [D124]: `.data` always resolves — class-level None


# ------------------------------------------------------- Quiver pilot ([D122])


_FIELD = {
    "x": np.array([0.0, 1.0, 2.0]),
    "y": np.array([0.0, 0.5, 1.0]),
    "u": np.array([1.0, 0.0, -1.0]),
    "v": np.array([0.0, 1.0, 0.5]),
}


def _quiver(**kw) -> qv.Quiver:
    return qv.Quiver(dict(_FIELD), x="x", y="y", u="u", v="v", **kw)


def test_quiver_lowers_to_the_resolved_segment_geometry():
    q = _quiver(line_width=2.0, alpha=0.5, color="red")
    lowered = q.lower(CTX)
    (sx, sy), (hx, hy) = q.resolved_segments()

    assert isinstance(lowered, Lowered) and len(lowered.marks) == 2
    shafts, heads = lowered.marks
    assert isinstance(shafts, Polyline) and isinstance(heads, Polyline)
    for mark, (gx, gy) in ((shafts, (sx, sy)), (heads, (hx, hy))):
        assert np.array_equal(mark.x, gx, equal_nan=True)
        assert np.array_equal(mark.y, gy, equal_nan=True)
        assert mark.stroke == Stroke(qv.Color("red"), width=2.0, alpha=0.5)


def test_quiver_default_color_is_the_series_palette_slot():
    lowered = _quiver().lower(LowerContext(theme=THEME, series_index=2))
    assert lowered.marks[0].stroke.color == THEME.palette[2]


def test_quiver_legend_routes_through_legend_entry():
    assert _quiver().lower(CTX).legend is None  # no label, no key
    keyed = _quiver(key=10.0, key_label="10 m/s").lower(CTX)
    assert keyed.legend is not None and keyed.legend.glyph == "arrow"  # [D112]


# ------------------------------------------- perturbation guard preview ([D123])

_NON_DEFAULT = {
    "arrow_scale": 2.5,
    "head_scale": 2.0,
    "color": "red",
    "line_width": 3.0,
    "alpha": 0.5,
    "label": "field",
    "key": 5.0,
    "key_label": "5 m/s",
}
_PREREQ = {"key_label": {"key": 5.0}}  # key_label alone is invalid by construction


@pytest.mark.parametrize("option", sorted(qv.Quiver.HONORED_BY_LOWERING))
def test_quiver_honored_options_visibly_change_the_lowering(option):
    prereq = _PREREQ.get(option, {})
    base = _quiver(**prereq).lower(CTX)
    perturbed = _quiver(**{**prereq, option: _NON_DEFAULT[option]}).lower(CTX)
    assert not structurally_equal(base, perturbed), (
        f"Quiver declares {option!r} honored by lowering, but perturbing it "
        f"left the Lowered unchanged — the declaration is dishonest")


def test_quiver_identity_fields_do_not_change_the_lowering():
    base = _quiver().lower(CTX)
    for kw in ({"id": "abc123"}, {"backend_hint": "matplotlib"}):
        assert structurally_equal(base, _quiver(**kw).lower(CTX))
