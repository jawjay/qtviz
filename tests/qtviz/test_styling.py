"""Tier-1 — Color, Palette, Options (spec §2.11–§2.13).

Color is the canonical, immutable, context-free color type (a value, never a
column — §2.11/Q-A). Palette wraps ordered colors with discrete/continuous
semantics. Built-in palettes must register without the optional matplotlib
extra (§2.12). Options stays small, universal, and hashable.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1


# ── Color ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("spec", ["red", "#ff0000", (1.0, 0.0, 0.0)])
def test_color_parses_every_form_to_rgba(spec):
    c = qv.Color(spec)
    r, g, b, a = c.rgba
    assert (round(r), round(g), round(b)) == (1, 0, 0)
    assert all(0.0 <= ch <= 1.0 for ch in c.rgba)


def test_color_construction_is_idempotent():
    red = qv.Color("red")
    assert qv.Color(red).rgba == red.rgba


def test_color_is_immutable_and_hashable():
    c = qv.Color("blue")
    assert hash(c) == hash(qv.Color("blue"))
    with pytest.raises(AttributeError):
        c.rgba = (0, 0, 0, 1)  # type: ignore[misc]


def test_color_backend_translations():
    c = qv.Color("#3366cc")
    assert c.hex().lower().lstrip("#") == "3366cc"
    assert isinstance(c.css(), str)
    QtGui = pytest.importorskip("PySide6.QtGui")
    assert isinstance(c.qt(), QtGui.QColor)


# ── Palette ──────────────────────────────────────────────────────────────────
def test_palette_from_hex_indexes_to_colors():
    p = qv.Palette.from_hex(["#000000", "#ffffff"])
    assert p[0].rgba[:3] == (0.0, 0.0, 0.0)
    assert p[1].rgba[:3] == (1.0, 1.0, 1.0)


def test_palette_continuous_interpolates_endpoints():
    p = qv.Palette.from_hex(["#000000", "#ffffff"], kind="continuous")
    assert p.at(0.0).rgba[:3] == (0.0, 0.0, 0.0)
    assert p.at(1.0).rgba[:3] == (1.0, 1.0, 1.0)
    mid = p.at(0.5).rgba[0]
    assert 0.3 < mid < 0.7  # halfway grey


def test_builtin_palettes_register_without_matplotlib():
    # viridis must be vendored as hex, not built via from_matplotlib (§2.12).
    assert "viridis" in qv.palettes.list()
    assert qv.palettes.get("viridis") is not None


# ── Options (deprecated [D51]; these guard it still behaves until removal) ─────
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_options_alpha_validation():
    qv.Options(alpha=0.5)  # ok
    with pytest.raises(ValueError):
        qv.Options(alpha=2.0)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_options_immutable_and_value_equal():
    o = qv.Options(color="red", alpha=0.5)
    assert o == qv.Options(color="red", alpha=0.5)
    assert hash(o) == hash(qv.Options(color="red", alpha=0.5))
    with pytest.raises(AttributeError):
        o.alpha = 0.1  # type: ignore[misc]
