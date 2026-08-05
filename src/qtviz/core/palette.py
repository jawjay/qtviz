"""`Palette` — ordered Colors with discrete/continuous semantics (spec §2.12).

Built-ins are vendored as hex stops so the core registry populates without the
optional matplotlib extra. `from_matplotlib` / `from_qt` stay available for
users who have those libraries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from ..errors import ValidationError
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
            raise ValidationError("Palette needs at least one color")
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
        import matplotlib  # noqa: PLC0415

        cmap = matplotlib.colormaps[name]
        stops: list[tuple[float, float, float, float]] = []
        for i in range(n):
            r, g, b, a = cmap(i / (n - 1))
            stops.append((r, g, b, a))
        return cls(stops, name=name, kind="continuous")

    @classmethod
    def from_qt(cls, palette) -> Palette:
        from PySide6.QtGui import QPalette  # noqa: PLC0415

        roles = (QPalette.ColorRole.Highlight, QPalette.ColorRole.Link,
                 QPalette.ColorRole.WindowText, QPalette.ColorRole.Text)
        cols = [palette.color(r).getRgbF() for r in roles]
        return cls(cols, name="qt")


class _PaletteRegistry:
    """The built-in palette registry, exposed as `qtviz.palettes`.

    `palettes.get("viridis")` / `palettes["viridis"]` look up a palette;
    `palettes.list()` (or iteration) names them all; `palettes.register()`
    adds your own. `Palette.from_matplotlib("...")` converts any matplotlib
    colormap when that extra is installed."""

    def __init__(self) -> None:
        self._p: dict[str, Palette] = {}

    def register(self, name: str, palette: Palette) -> None:
        self._p[name] = palette

    def get(self, name: str) -> Palette:
        try:
            return self._p[name]
        except KeyError:
            import difflib  # noqa: PLC0415

            from ..errors import ValidationError  # noqa: PLC0415

            close = difflib.get_close_matches(name, self._p, n=3, cutoff=0.6)
            hint = f"; did you mean {', '.join(repr(c) for c in close)}?" if close else ""
            raise ValidationError(
                f"no palette named {name!r}{hint} (registered: {sorted(self._p)}; "
                f"Palette.from_matplotlib() converts any matplotlib colormap)"
            ) from None

    def __getitem__(self, name: str) -> Palette:
        return self.get(name)

    def __iter__(self):
        return iter(self._p)

    def __len__(self) -> int:
        return len(self._p)

    def __contains__(self, name: object) -> bool:
        return name in self._p

    def list(self) -> list[str]:
        return list(self._p)

    def __repr__(self) -> str:
        return f"palettes({', '.join(sorted(self._p))})"


# Perceptually-uniform continuous ramps (matplotlib's stops, 10 samples each)
# + the categorical default — vendored so the registry needs no extra.
_MAGMA = (
    "#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f",
    "#cd4071", "#f1605d", "#fd9567", "#fec98d", "#fcfdbf",
)
_PLASMA = (
    "#0d0887", "#47039f", "#7301a8", "#9c179e", "#bd3786",
    "#d8576b", "#ed7953", "#fa9e3b", "#fdc926", "#f0f921",
)
_INFERNO = (
    "#000004", "#1b0c42", "#4b0c6b", "#781c6d", "#a52c60",
    "#cf4446", "#ed6925", "#fb9a06", "#f7d03c", "#fcffa4",
)
_CIVIDIS = (
    "#00204d", "#00336f", "#39486b", "#575d6d", "#707173",
    "#8a8779", "#a69d75", "#c4b56c", "#e4cf5b", "#ffea46",
)
_GRAY = ("#000000", "#1c1c1c", "#383838", "#555555", "#717171",
         "#8d8d8d", "#aaaaaa", "#c6c6c6", "#e2e2e2", "#ffffff")
_CATEGORY20 = (
    "#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78", "#2ca02c",
    "#98df8a", "#d62728", "#ff9896", "#9467bd", "#c5b0d5",
    "#8c564b", "#c49c94", "#e377c2", "#f7b6d2", "#7f7f7f",
    "#c7c7c7", "#bcbd22", "#dbdb8d", "#17becf", "#9edae5",
)

palettes = _PaletteRegistry()
palettes.register("viridis", Palette.from_hex(_VIRIDIS, name="viridis", kind="continuous"))
palettes.register("magma", Palette.from_hex(_MAGMA, name="magma", kind="continuous"))
palettes.register("plasma", Palette.from_hex(_PLASMA, name="plasma", kind="continuous"))
palettes.register("inferno", Palette.from_hex(_INFERNO, name="inferno", kind="continuous"))
palettes.register("cividis", Palette.from_hex(_CIVIDIS, name="cividis", kind="continuous"))
palettes.register("gray", Palette.from_hex(_GRAY, name="gray", kind="continuous"))
palettes.register("category10", Palette.from_hex(_CATEGORY10, name="category10"))
palettes.register("category20", Palette.from_hex(_CATEGORY20, name="category20"))
