"""`Theme` — backend-agnostic visual styling (spec §2.13).

Migrated from the qtwebplot string-based theme: colors are now `Color`, the
categorical palette is a `Palette`, and font sizes are carried. Each backend
translates a Theme to native form via its own `apply_theme`.
"""

from __future__ import annotations

from ._immutable import Immutable
from .color import Color, ColorSpec
from .palette import _CATEGORY10, Palette

_DARK_CATEGORY = (
    "#5fa8ff", "#ffa64d", "#7bd47b", "#ff6b6b", "#c08bff",
    "#d8a584", "#ff9ed8", "#bfbfbf", "#dde04f", "#5fdfff",
)


class Theme(Immutable):
    def __init__(
        self,
        *,
        background: ColorSpec = "#ffffff",
        foreground: ColorSpec = "#222222",
        grid: ColorSpec = "#dddddd",
        palette: Palette | None = None,
        font_family: str = "sans-serif",
        font_size: int = 10,
        title_size: int = 12,
    ) -> None:
        self.background = Color(background)
        self.foreground = Color(foreground)
        self.grid = Color(grid)
        self.palette = palette if palette is not None else Palette.from_hex(_CATEGORY10)
        self.font_family = font_family
        self.font_size = font_size
        self.title_size = title_size
        self._freeze()

    @property
    def is_dark(self) -> bool:
        r, g, b, _ = self.background.rgba
        return (0.299 * r + 0.587 * g + 0.114 * b) < 0.5

    @classmethod
    def light(cls) -> Theme:
        return cls(background="#ffffff", foreground="#222222", grid="#e6e6e6",
                   palette=Palette.from_hex(_CATEGORY10))

    @classmethod
    def dark(cls) -> Theme:
        return cls(background="#1e1e1e", foreground="#e6e6e6", grid="#3a3a3a",
                   palette=Palette.from_hex(_DARK_CATEGORY))

    @classmethod
    def from_qt_palette(cls, palette, *, font_family: str = "sans-serif") -> Theme:
        from PySide6.QtGui import QColor, QPalette  # noqa: PLC0415

        bg = palette.color(QPalette.ColorRole.Window)
        fg = palette.color(QPalette.ColorRole.WindowText)
        is_dark = bg.lightness() < 128
        grid = QColor(
            int(bg.red() * 0.85 + fg.red() * 0.15),
            int(bg.green() * 0.85 + fg.green() * 0.15),
            int(bg.blue() * 0.85 + fg.blue() * 0.15),
        )
        cat = _DARK_CATEGORY if is_dark else _CATEGORY10
        return cls(background=bg.name(), foreground=fg.name(), grid=grid.name(),
                   palette=Palette.from_hex(cat), font_family=font_family)

    @classmethod
    def from_qt_app(cls, app=None) -> Theme:
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415

        app = app or QApplication.instance()
        if app is None:
            raise RuntimeError(
                "Theme.from_qt_app() needs an existing QApplication; "
                "construct it first or use Theme.light()/dark()."
            )
        return cls.from_qt_palette(app.palette(), font_family=app.font().family())
