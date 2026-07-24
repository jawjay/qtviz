"""Annotation / reference elements ([D70], milestone-0.4 §1).

Data-less pure-data elements — a reference line, a band, a text note. No
`DataRef`: like `RawFigure` they pass through the resolve pipeline untouched.
They compose via `*` like any element, default to the theme's *foreground* (a
reference is chrome, not a series — it must not look like palette data), and a
labeled one contributes a neutral `legend_entry()`.

Interactivity (dragging a threshold line, resizing a region) is deliberately
not modeled — reach the live `InfiniteLine` / `LinearRegionItem` through
`handle.native(element_id)` ([D53])."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..errors import ValidationError


class _Reference(Element):
    """Shared base: neutral legend swatch (theme foreground, not a palette slot)."""

    label: str | None  # declared for typing; Text carries no label

    def legend_entry(self, theme, index: int = 0):
        if getattr(self, "label", None) is None:
            return None
        from ..core.color import Color  # noqa: PLC0415
        from ..core.encoding import LegendEntry  # noqa: PLC0415

        spec = getattr(self, "color", None)
        swatch = Color(spec) if spec is not None else theme.foreground
        return LegendEntry(str(self.label), swatch)


class HLine(_Reference):
    """A horizontal reference line at `y`, spanning the full x extent."""

    REQUIRED_OPTIONS = ("y",)
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "alpha", "label")

    def __init__(
        self,
        y: float,
        *,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        line_style: Literal["solid", "dashed", "dotted", "dashdot"] = "solid",
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who=type(self).__name__)
        self.y = float(y)
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.alpha = alpha
        self.label = label
        self._freeze()


class VLine(_Reference):
    """A vertical reference line at `x`, spanning the full y extent."""

    REQUIRED_OPTIONS = ("x",)
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "alpha", "label")

    def __init__(
        self,
        x: float,
        *,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        line_style: Literal["solid", "dashed", "dotted", "dashdot"] = "solid",
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who=type(self).__name__)
        self.x = float(x)
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.alpha = alpha
        self.label = label
        self._freeze()


class Span(_Reference):
    """A filled reference band from `lo` to `hi` — horizontal (`orient="h"`, a
    y-range across the full width) or vertical (`orient="v"`, an x-range)."""

    REQUIRED_OPTIONS = ("lo", "hi")
    RECOMMENDED_OPTIONS = ("color", "alpha", "label")

    def __init__(
        self,
        lo: float,
        hi: float,
        *,
        orient: Literal["h", "v"] = "h",
        color: ColorSpec | None = None,
        alpha: float = 0.25,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if orient not in ("h", "v"):
            raise ValidationError(f"Span orient must be 'h' or 'v', got {orient!r}")
        if not float(lo) < float(hi):
            raise ValidationError(f"Span requires lo < hi, got ({lo!r}, {hi!r})")
        check_alpha(alpha, who="Span")
        self.lo, self.hi = float(lo), float(hi)
        self.orient = orient
        self.color = color
        self.alpha = alpha
        self.label = label
        self._freeze()


class Text(_Reference):
    """A text note anchored at data coordinates `(x, y)`."""

    REQUIRED_OPTIONS = ("x", "y", "text")
    RECOMMENDED_OPTIONS = ("color", "size", "anchor")

    def __init__(
        self,
        x: float,
        y: float,
        text: str,
        *,
        color: ColorSpec | None = None,
        size: float | None = None,
        anchor: Literal["center", "left", "right"] = "center",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if anchor not in ("center", "left", "right"):
            raise ValidationError(f"Text anchor must be center|left|right, got {anchor!r}")
        self.x, self.y = float(x), float(y)
        self.text = str(text)
        self.color = color
        self.size = size
        self.anchor = anchor
        self._freeze()


ANNOTATION_TYPES: tuple[type, ...] = (HLine, VLine, Span, Text)
