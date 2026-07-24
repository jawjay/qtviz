"""`Palette` — ordered Colors with discrete/continuous semantics (spec §2.12).

Built-ins are vendored as hex stops so the core registry populates without the
optional matplotlib extra. `from_matplotlib` / `from_qt` stay available for
users who have those libraries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from ._immutable import Immutable
from .color import Color, ColorSpec

# Vendored stops (no matplotlib dependency at import).
_VIRIDIS = (
    "#440154", "#482878", "#3e4a89", "#31688e", "#26828e",
    "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725",
)
_CATEGORY10 = (
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
)


class Palette(Immutable):
    """An ordered, cycling sequence of colors used for categorical encoding."""

    def __init__(
        self,
        colors: Sequence[ColorSpec],
        *,
        name: str | None = None,
        kind: Literal["discrete", "continuous"] = "discrete",
    ) -> None:
        self.colors = tuple(Color(c) for c in colors)
        self.name = name
        self.kind = kind
        if not self.colors:
            raise ValueError("Palette needs at least one color")
        self._freeze()

    def at(self, t: float) -> Color:
        """t in [0, 1]. Discrete: bucketize. Continuous: linear interpolation."""
        t = min(1.0, max(0.0, float(t)))
        n = len(self.colors)
        if n == 1:
            return self.colors[0]
        if self.kind == "discrete":
            return self.colors[min(n - 1, int(t * n))]
        pos = t * (n - 1)
        i = int(pos)
        if i >= n - 1:
            return self.colors[-1]
        frac = pos - i
        a, b = self.colors[i].rgba, self.colors[i + 1].rgba
        mixed = tuple(a[k] + (b[k] - a[k]) * frac for k in range(4))
        return Color((mixed[0], mixed[1], mixed[2], mixed[3]))

    def __getitem__(self, i: int) -> Color:
        return self.colors[i]

    def __len__(self) -> int:
        return len(self.colors)

    def __iter__(self):
        return iter(self.colors)

    @classmethod
    def from_hex(cls, hexes, *, name=None, kind="discrete") -> Palette:
        return cls(hexes, name=name, kind=kind)

    @classmethod
    def from_matplotlib(cls, name: str, *, n: int = 10) -> Palette:
        import matplotlib.cm as cm  # noqa: PLC0415

        cmap = cm.get_cmap(name)  # type: ignore[attr-defined]  # mpl<3.9 API kept for compat
        stops = [tuple(cmap(i / (n - 1)))[:4] for i in range(n)]
        return cls(stops, name=name, kind="continuous")

    @classmethod
    def from_qt(cls, palette) -> Palette:
        from PySide6.QtGui import QPalette  # noqa: PLC0415

        roles = (QPalette.ColorRole.Highlight, QPalette.ColorRole.Link,
                 QPalette.ColorRole.WindowText, QPalette.ColorRole.Text)
        cols = [palette.color(r).getRgbF() for r in roles]
        return cls(cols, name="qt")


class _PaletteRegistry:
    def __init__(self) -> None:
        self._p: dict[str, Palette] = {}

    def register(self, name: str, palette: Palette) -> None:
        self._p[name] = palette

    def get(self, name: str) -> Palette:
        return self._p[name]

    def list(self) -> list[str]:
        return list(self._p)


palettes = _PaletteRegistry()
palettes.register("viridis", Palette.from_hex(_VIRIDIS, name="viridis", kind="continuous"))
palettes.register("category10", Palette.from_hex(_CATEGORY10, name="category10"))
