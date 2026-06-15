"""Theme — backend-agnostic visual styling, derivable from a Qt palette.

A `Theme` is data: background / foreground / grid colors, a categorical
trace palette, and a font family. Backends translate it into their native
theming (Plotly template, Bokeh `Theme`, etc.) via `apply_theme(theme)`.

The most useful constructor is `Theme.from_qt_app()` — it pulls colors and
the font from `QApplication.palette()` / `QApplication.font()`, so embedded
plots match the host app's light/dark mode by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QPalette


# Categorical palettes — d3.schemeCategory10 reads well on both light and
# dark backgrounds, with a slightly brightened variant for dark mode.
_PALETTE_LIGHT: tuple[str, ...] = (
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
)
_PALETTE_DARK: tuple[str, ...] = (
    "#5fa8ff", "#ffa64d", "#7bd47b", "#ff6b6b", "#c08bff",
    "#d8a584", "#ff9ed8", "#bfbfbf", "#dde04f", "#5fdfff",
)


@dataclass(frozen=True)
class Theme:
    """Visual theme. Self-contained — backends translate to native forms."""

    background: str = "#ffffff"
    foreground: str = "#222222"
    grid: str = "#dddddd"
    palette: tuple[str, ...] = _PALETTE_LIGHT
    font_family: str = "sans-serif"

    # ── factories ────────────────────────────────────────────────────────
    @classmethod
    def light(cls) -> Theme:
        return cls(
            background="#ffffff",
            foreground="#222222",
            grid="#e6e6e6",
            palette=_PALETTE_LIGHT,
            font_family="sans-serif",
        )

    @classmethod
    def dark(cls) -> Theme:
        return cls(
            background="#1e1e1e",
            foreground="#e6e6e6",
            grid="#3a3a3a",
            palette=_PALETTE_DARK,
            font_family="sans-serif",
        )

    @classmethod
    def from_qt_palette(
        cls,
        palette: QPalette,
        *,
        font_family: str = "sans-serif",
    ) -> Theme:
        """Derive a Theme from a Qt palette.

        Uses `Window` for background, `WindowText` for foreground, and picks
        the light or dark categorical palette based on the background's
        lightness.
        """
        from PySide6.QtGui import QColor, QPalette  # noqa: PLC0415

        bg_color = palette.color(QPalette.ColorRole.Window)
        fg_color = palette.color(QPalette.ColorRole.WindowText)
        bg_hex = bg_color.name()
        fg_hex = fg_color.name()

        is_dark = bg_color.lightness() < 128
        traces = _PALETTE_DARK if is_dark else _PALETTE_LIGHT

        # Grid color: blend background toward foreground by ~15%.
        grid = QColor(
            int(bg_color.red() * 0.85 + fg_color.red() * 0.15),
            int(bg_color.green() * 0.85 + fg_color.green() * 0.15),
            int(bg_color.blue() * 0.85 + fg_color.blue() * 0.15),
        ).name()

        return cls(
            background=bg_hex,
            foreground=fg_hex,
            grid=grid,
            palette=traces,
            font_family=font_family,
        )

    @classmethod
    def from_qt_app(cls, app=None) -> Theme:
        """Convenience: derive from `QApplication.palette()` and `font()`.

        Raises if no `QApplication` exists yet.
        """
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415

        if app is None:
            app = QApplication.instance()
        if app is None:
            raise RuntimeError(
                "Theme.from_qt_app() needs an existing QApplication. "
                "Construct it before calling, or use Theme.light()/dark()."
            )
        return cls.from_qt_palette(app.palette(), font_family=app.font().family())

    # ── derived attributes ───────────────────────────────────────────────
    @property
    def is_dark(self) -> bool:
        from PySide6.QtGui import QColor  # noqa: PLC0415

        return QColor(self.background).lightness() < 128
