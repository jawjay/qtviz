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
    """A text note anchored at data coordinates `(x, y)`; `rotation` is
    counter-clockwise degrees, `anchor`/`anchor_v` place the box relative to
    the point, and `frame=True` draws a theme-styled box behind it ([D96])."""

    REQUIRED_OPTIONS = ("x", "y", "text")
    RECOMMENDED_OPTIONS = ("color", "size", "anchor", "anchor_v", "rotation", "frame")

    def __init__(
        self,
        x: float,
        y: float,
        text: str,
        *,
        color: ColorSpec | None = None,
        size: float | None = None,
        anchor: Literal["center", "left", "right"] = "center",
        anchor_v: Literal["center", "top", "bottom"] = "center",
        rotation: float = 0.0,
        frame: bool = False,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if anchor not in ("center", "left", "right"):
            raise ValidationError(f"Text anchor must be center|left|right, got {anchor!r}")
        if anchor_v not in ("center", "top", "bottom"):
            raise ValidationError(
                f"Text anchor_v must be center|top|bottom, got {anchor_v!r}"
            )
        self.x, self.y = float(x), float(y)
        self.text = str(text)
        self.color = color
        self.size = size
        self.anchor = anchor
        self.anchor_v = anchor_v
        self.rotation = float(rotation)
        self.frame = bool(frame)
        self._freeze()


_HEADS = ("end", "both", "none")


class Arrow(_Reference):
    """An arrow between two data points, head at the end point (`head="end"`,
    or `"both"`/`"none"`) — the pointing half of `annotate` ([D96]); pair with
    a `Text` for a callout."""

    REQUIRED_OPTIONS = ("x0", "y0", "x1", "y1")
    RECOMMENDED_OPTIONS = ("head", "color", "line_width", "alpha", "label")

    def __init__(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        head: Literal["end", "both", "none"] = "end",
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if head not in _HEADS:
            raise ValidationError(f"Arrow head must be one of {_HEADS}, got {head!r}")
        check_alpha(alpha, who="Arrow")
        self.x0, self.y0 = float(x0), float(y0)
        self.x1, self.y1 = float(x1), float(y1)
        self.head = head
        self.color = color
        self.line_width = line_width
        self.alpha = alpha
        self.label = label
        self._freeze()


from .shapes import Ellipse, Polygon, Rect  # noqa: E402 — shapes share the class

ANNOTATION_TYPES: tuple[type, ...] = (HLine, VLine, Span, Text, Arrow,
                                      Rect, Ellipse, Polygon)
