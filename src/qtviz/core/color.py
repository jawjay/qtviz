"""`Color` — the canonical, immutable, context-free color type (spec §2.11).

`color=` is always a color value; data-driven coloring is a separate
`color_by=` column (§2.11 / Q-A), so there is no column/color ambiguity at the
type level. Construct from a name, hex, or rgb(a) tuple; translate to each
backend's native form.
"""

from __future__ import annotations

from typing import Union

ColorSpec = Union[str, tuple[float, float, float], tuple[float, float, float, float], "Color"]

# A small CSS-named set; same names HTML/CSS use.
_KNOWN: dict[str, tuple[float, float, float]] = {
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
    "red": (1.0, 0.0, 0.0),
    "green": (0.0, 0.502, 0.0),
    "lime": (0.0, 1.0, 0.0),
    "blue": (0.0, 0.0, 1.0),
    "yellow": (1.0, 1.0, 0.0),
    "cyan": (0.0, 1.0, 1.0),
    "magenta": (1.0, 0.0, 1.0),
    "gray": (0.502, 0.502, 0.502),
    "grey": (0.502, 0.502, 0.502),
    "orange": (1.0, 0.647, 0.0),
    "purple": (0.502, 0.0, 0.502),
    "brown": (0.647, 0.165, 0.165),
    "pink": (1.0, 0.753, 0.796),
    "transparent": (0.0, 0.0, 0.0),
}


def _parse(spec: ColorSpec) -> tuple[float, float, float, float]:
    if isinstance(spec, Color):
        return spec._rgba
    if isinstance(spec, str):
        s = spec.strip().lower()
        if s == "transparent":
            return (0.0, 0.0, 0.0, 0.0)
        if s in _KNOWN:
            r, g, b = _KNOWN[s]
            return (r, g, b, 1.0)
        if s.startswith("#"):
            return _parse_hex(s)
        raise ValueError(f"unknown color name {spec!r}")
    if isinstance(spec, (tuple, list)):
        vals = tuple(float(v) for v in spec)
        if len(vals) == 3:
            vals = vals + (1.0,)
        if len(vals) != 4:
            raise ValueError(f"color tuple must be (r,g,b) or (r,g,b,a), got {spec!r}")
        if not all(0.0 <= v <= 1.0 for v in vals):
            raise ValueError(f"color channels must be in [0, 1], got {spec!r}")
        return vals  # type: ignore[return-value]
    raise TypeError(f"cannot make a Color from {type(spec).__name__}")


def _parse_hex(s: str) -> tuple[float, float, float, float]:
    h = s.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    if len(h) != 8:
        raise ValueError(f"hex color must be #rgb, #rrggbb or #rrggbbaa, got {s!r}")
    try:
        r, g, b, a = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
    except ValueError:
        raise ValueError(f"invalid hex color {s!r}") from None
    return (r, g, b, a)


class Color:
    """Immutable canonical color. str / tuple inputs auto-convert."""

    __slots__ = ("_rgba",)

    def __init__(self, spec: ColorSpec) -> None:
        object.__setattr__(self, "_rgba", _parse(spec))

    def __setattr__(self, *_a) -> None:
        raise AttributeError("Color is immutable")

    @property
    def rgba(self) -> tuple[float, float, float, float]:
        return self._rgba

    def hex(self) -> str:
        r, g, b, a = (round(c * 255) for c in self._rgba)
        return f"#{r:02x}{g:02x}{b:02x}" if a == 255 else f"#{r:02x}{g:02x}{b:02x}{a:02x}"

    def css(self) -> str:
        r, g, b, a = self._rgba
        return f"rgba({round(r * 255)}, {round(g * 255)}, {round(b * 255)}, {a:.3g})"

    def mpl(self) -> tuple[float, float, float, float]:
        return self._rgba

    def qt(self):  # -> QColor
        from PySide6.QtGui import QColor  # noqa: PLC0415

        r, g, b, a = self._rgba
        return QColor.fromRgbF(r, g, b, a)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Color) and self._rgba == other._rgba

    def __hash__(self) -> int:
        return hash(self._rgba)

    def __repr__(self) -> str:
        return f"Color({self.hex()!r})"
