"""`Color` — the canonical, immutable, context-free color type (spec §2.11).

`color=` is always a color value; data-driven coloring is a separate
`color_by=` column (§2.11 / Q-A), so there is no column/color ambiguity at the
type level. Construct from a name, hex, or rgb(a) tuple; translate to each
backend's native form.
"""

from __future__ import annotations

from typing import Union

from ..errors import ValidationError

ColorSpec = Union[str, tuple[float, float, float], tuple[float, float, float, float], "Color"]

# The full CSS4 / X11 named-color set ([D143]) — the names matplotlib, CSS, and
# SVG all agree on — vendored as hex so lookup needs no optional dependency.
_KNOWN: dict[str, str] = {
    "aliceblue": "#f0f8ff", "antiquewhite": "#faebd7", "aqua": "#00ffff",
    "aquamarine": "#7fffd4", "azure": "#f0ffff", "beige": "#f5f5dc",
    "bisque": "#ffe4c4", "black": "#000000", "blanchedalmond": "#ffebcd",
    "blue": "#0000ff", "blueviolet": "#8a2be2", "brown": "#a52a2a",
    "burlywood": "#deb887", "cadetblue": "#5f9ea0", "chartreuse": "#7fff00",
    "chocolate": "#d2691e", "coral": "#ff7f50", "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc", "crimson": "#dc143c", "cyan": "#00ffff",
    "darkblue": "#00008b", "darkcyan": "#008b8b", "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9", "darkgreen": "#006400", "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b", "darkmagenta": "#8b008b", "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00", "darkorchid": "#9932cc", "darkred": "#8b0000",
    "darksalmon": "#e9967a", "darkseagreen": "#8fbc8f", "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f", "darkslategrey": "#2f4f4f", "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3", "deeppink": "#ff1493", "deepskyblue": "#00bfff",
    "dimgray": "#696969", "dimgrey": "#696969", "dodgerblue": "#1e90ff",
    "firebrick": "#b22222", "floralwhite": "#fffaf0", "forestgreen": "#228b22",
    "fuchsia": "#ff00ff", "gainsboro": "#dcdcdc", "ghostwhite": "#f8f8ff",
    "gold": "#ffd700", "goldenrod": "#daa520", "gray": "#808080",
    "green": "#008000", "greenyellow": "#adff2f", "grey": "#808080",
    "honeydew": "#f0fff0", "hotpink": "#ff69b4", "indianred": "#cd5c5c",
    "indigo": "#4b0082", "ivory": "#fffff0", "khaki": "#f0e68c",
    "lavender": "#e6e6fa", "lavenderblush": "#fff0f5", "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd", "lightblue": "#add8e6", "lightcoral": "#f08080",
    "lightcyan": "#e0ffff", "lightgoldenrodyellow": "#fafad2", "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90", "lightgrey": "#d3d3d3", "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a", "lightseagreen": "#20b2aa", "lightskyblue": "#87cefa",
    "lightslategray": "#778899", "lightslategrey": "#778899", "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0", "lime": "#00ff00", "limegreen": "#32cd32",
    "linen": "#faf0e6", "magenta": "#ff00ff", "maroon": "#800000",
    "mediumaquamarine": "#66cdaa", "mediumblue": "#0000cd", "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db", "mediumseagreen": "#3cb371", "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a", "mediumturquoise": "#48d1cc", "mediumvioletred": "#c71585",
    "midnightblue": "#191970", "mintcream": "#f5fffa", "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5", "navajowhite": "#ffdead", "navy": "#000080",
    "oldlace": "#fdf5e6", "olive": "#808000", "olivedrab": "#6b8e23",
    "orange": "#ffa500", "orangered": "#ff4500", "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa", "palegreen": "#98fb98", "paleturquoise": "#afeeee",
    "palevioletred": "#db7093", "papayawhip": "#ffefd5", "peachpuff": "#ffdab9",
    "peru": "#cd853f", "pink": "#ffc0cb", "plum": "#dda0dd",
    "powderblue": "#b0e0e6", "purple": "#800080", "rebeccapurple": "#663399",
    "red": "#ff0000", "rosybrown": "#bc8f8f", "royalblue": "#4169e1",
    "saddlebrown": "#8b4513", "salmon": "#fa8072", "sandybrown": "#f4a460",
    "seagreen": "#2e8b57", "seashell": "#fff5ee", "sienna": "#a0522d",
    "silver": "#c0c0c0", "skyblue": "#87ceeb", "slateblue": "#6a5acd",
    "slategray": "#708090", "slategrey": "#708090", "snow": "#fffafa",
    "springgreen": "#00ff7f", "steelblue": "#4682b4", "tan": "#d2b48c",
    "teal": "#008080", "thistle": "#d8bfd8", "tomato": "#ff6347",
    "turquoise": "#40e0d0", "violet": "#ee82ee", "wheat": "#f5deb3",
    "white": "#ffffff", "whitesmoke": "#f5f5f5", "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}


def _unknown_name_error(spec: str) -> ValidationError:
    import difflib  # noqa: PLC0415

    close = difflib.get_close_matches(spec.strip().lower(), _KNOWN, n=3, cutoff=0.6)
    hint = f"; did you mean {', '.join(repr(c) for c in close)}?" if close else ""
    return ValidationError(
        f"unknown color name {spec!r}{hint} "
        f"(CSS4 names, '#rrggbb' hex, or an (r, g, b[, a]) tuple are accepted)"
    )


def _parse(spec: ColorSpec) -> tuple[float, float, float, float]:
    if isinstance(spec, Color):
        return spec._rgba
    if isinstance(spec, str):
        s = spec.strip().lower()
        if s == "transparent":
            return (0.0, 0.0, 0.0, 0.0)
        if s in _KNOWN:
            return _parse_hex(_KNOWN[s])
        if s.startswith("#"):
            return _parse_hex(s)
        raise _unknown_name_error(spec)
    if isinstance(spec, (tuple, list)):
        vals = tuple(float(v) for v in spec)
        if len(vals) == 3:
            vals = vals + (1.0,)
        if len(vals) != 4:
            raise ValidationError(f"color tuple must be (r,g,b) or (r,g,b,a), got {spec!r}")
        if not all(0.0 <= v <= 1.0 for v in vals):
            raise ValidationError(f"color channels must be in [0, 1], got {spec!r}")
        return vals  # type: ignore[return-value]
    raise TypeError(f"cannot make a Color from {type(spec).__name__}")


def _parse_hex(s: str) -> tuple[float, float, float, float]:
    h = s.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    if len(h) != 8:
        raise ValidationError(f"hex color must be #rgb, #rrggbb or #rrggbbaa, got {s!r}")
    try:
        r, g, b, a = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
    except ValueError:
        raise ValidationError(f"invalid hex color {s!r}") from None
    return (r, g, b, a)


class Color:
    """Immutable canonical color. str / tuple inputs auto-convert."""

    _rgba: tuple[float, float, float, float]

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
