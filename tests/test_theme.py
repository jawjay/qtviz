"""Theme unit tests — no QApplication needed for the dataclass shape;
the Qt-derived factories do need one.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from qtviz.backends.webengine.theme import Theme


def test_theme_defaults_light():
    t = Theme()
    assert t.background == "#ffffff"
    assert t.foreground == "#222222"
    assert len(t.palette) >= 5
    assert not t.is_dark


def test_theme_light_dark_distinguishable():
    light = Theme.light()
    dark = Theme.dark()
    assert light.background != dark.background
    assert light.foreground != dark.foreground
    assert light.palette != dark.palette
    assert light.is_dark is False
    assert dark.is_dark is True


def test_theme_immutable():
    t = Theme.light()
    # FrozenInstanceError subclasses AttributeError, so this covers both
    with pytest.raises(AttributeError):
        t.background = "#000000"  # type: ignore[misc]


def test_from_qt_palette_picks_dark_for_dark_window():
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#101010"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#f0f0f0"))

    t = Theme.from_qt_palette(pal)
    assert t.background.lower() == "#101010"
    assert t.foreground.lower() == "#f0f0f0"
    assert t.is_dark


def test_from_qt_palette_picks_light_for_light_window():
    from PySide6.QtGui import QColor, QPalette

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#fafafa"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a1a"))

    t = Theme.from_qt_palette(pal)
    assert t.background.lower() == "#fafafa"
    assert not t.is_dark
