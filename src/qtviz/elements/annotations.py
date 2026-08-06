"""Annotation / reference elements (milestone-0.4 §1).

Data-less pure-data elements — a reference line, a band, a text note. No
`DataRef`: like `RawFigure` they pass through the resolve pipeline untouched.
They compose via `*` like any element, default to the theme's *foreground* (a
reference is chrome, not a series — it must not look like palette data), and a
labeled one contributes a neutral `legend_entry()`.

Interactivity (dragging a threshold line, resizing a region) is deliberately
not modeled — reach the live `InfiniteLine` / `LinearRegionItem` through
`handle.native(element_id)`."""

from __future__ import annotations

from typing import Literal

from ..core._validate import check_alpha, check_color
from ..core.color import ColorSpec
from ..core.element import Element, ElementId
from ..errors import ValidationError


class _Reference(Element):
    """Shared base: neutral legend swatch (theme foreground, not a palette slot)."""

    DATA_KIND = "none"  # [D124]: annotations are data-less; `.data` is the base None
    label: str | None  # declared for typing; Text carries no label

    def _ref_stroke(self, ctx):
        """Shared stroke: theme-foreground default, dash vocab."""
        from ..core.lowering import resolve_ref_color  # noqa: PLC0415
        from ..core.marks import Stroke  # noqa: PLC0415

        return Stroke(resolve_ref_color(self.color, ctx.theme),
                      width=self.line_width, dash=self.line_style, alpha=self.alpha)

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
        line_style: str | tuple[float, ...] = "solid",
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from .curve import check_line_style  # noqa: PLC0415 — shared [D99] guard

        check_alpha(alpha, who=type(self).__name__)
        check_color(color, who=type(self).__name__)
        check_line_style(line_style, who=type(self).__name__)
        self.y = float(y)
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.alpha = alpha
        self.label = label
        self._freeze()

    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def lower(self, ctx):
        from ..core.lowering import Lowered  # noqa: PLC0415
        from ..core.marks import Rule  # noqa: PLC0415

        return Lowered(marks=(Rule("h", self._ref_stroke(ctx), at=self.y),),
                       legend=self.legend_entry(ctx.theme, ctx.series_index))


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
        line_style: str | tuple[float, ...] = "solid",
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from .curve import check_line_style  # noqa: PLC0415 — shared [D99] guard

        check_alpha(alpha, who=type(self).__name__)
        check_color(color, who=type(self).__name__)
        check_line_style(line_style, who=type(self).__name__)
        self.x = float(x)
        self.color = color
        self.line_width = line_width
        self.line_style = line_style
        self.alpha = alpha
        self.label = label
        self._freeze()

    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def lower(self, ctx):
        from ..core.lowering import Lowered  # noqa: PLC0415
        from ..core.marks import Rule  # noqa: PLC0415

        return Lowered(marks=(Rule("v", self._ref_stroke(ctx), at=self.x),),
                       legend=self.legend_entry(ctx.theme, ctx.series_index))


class Span(_Reference):
    """A filled reference band from `lo` to `hi` — horizontal
    (`orient="horizontal"`, a y-range across the full width) or vertical
    (`orient="vertical"`, an x-range)."""

    REQUIRED_OPTIONS = ("lo", "hi")
    RECOMMENDED_OPTIONS = ("color", "alpha", "label")

    def __init__(
        self,
        lo: float,
        hi: float,
        *,
        orient: Literal["horizontal", "vertical"] = "horizontal",
        color: ColorSpec | None = None,
        alpha: float = 0.25,
        label: str | None = None,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if orient not in ("horizontal", "vertical"):
            raise ValidationError(
                f"Span orient must be 'horizontal' or 'vertical', got {orient!r}")
        if not float(lo) < float(hi):
            raise ValidationError(f"Span requires lo < hi, got ({lo!r}, {hi!r})")
        check_alpha(alpha, who="Span")
        check_color(color, who="Span")
        self.lo, self.hi = float(lo), float(hi)
        self.orient = orient
        self.color = color
        self.alpha = alpha
        self.label = label
        self._freeze()

    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def lower(self, ctx):
        from ..core.lowering import Lowered, resolve_ref_color  # noqa: PLC0415
        from ..core.marks import Fill, SpanMark  # noqa: PLC0415

        fill = Fill(resolve_ref_color(self.color, ctx.theme), self.alpha)
        code = "h" if self.orient == "horizontal" else "v"  # the mark IR keeps its short encoding
        return Lowered(marks=(SpanMark(code, self.lo, self.hi, fill),),
                       legend=self.legend_entry(ctx.theme, ctx.series_index))


class Text(_Reference):
    """A text note anchored at data coordinates `(x, y)`; `rotation` is
    counter-clockwise degrees, `halign`/`valign` place the box relative to
    the point, and `frame=True` draws a theme-styled box behind it."""

    REQUIRED_OPTIONS = ("x", "y", "text")
    RECOMMENDED_OPTIONS = ("color", "size", "halign", "valign", "rotation", "frame")

    def __init__(
        self,
        x: float,
        y: float,
        text: str,
        *,
        color: ColorSpec | None = None,
        size: float | None = None,
        halign: Literal["center", "left", "right"] = "center",
        valign: Literal["center", "top", "bottom"] = "center",
        rotation: float = 0.0,
        frame: bool = False,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_color(color, who="Text")
        if halign not in ("center", "left", "right"):
            raise ValidationError(f"Text halign must be center|left|right, got {halign!r}")
        if valign not in ("center", "top", "bottom"):
            raise ValidationError(
                f"Text valign must be center|top|bottom, got {valign!r}"
            )
        self.x, self.y = float(x), float(y)
        self.text = str(text)
        self.color = color
        self.size = size
        self.halign = halign
        self.valign = valign
        self.rotation = float(rotation)
        self.frame = bool(frame)
        self._freeze()

    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def lower(self, ctx):
        from ..core.lowering import Lowered, resolve_ref_color  # noqa: PLC0415
        from ..core.marks import TextMark  # noqa: PLC0415

        mark = TextMark(self.x, self.y, self.text,
                        color=resolve_ref_color(self.color, ctx.theme),
                        size=self.size, halign=self.halign, valign=self.valign,
                        rotation=self.rotation, frame=self.frame)
        return Lowered(marks=(mark,))


class RefLine(_Reference):
    """An infinite reference line `y = slope·x + intercept` (the
    `axline` analog; `HLine`/`VLine` cover the axis-parallel cases). A
    straight data-space line isn't straight under log scales, so it
    warns-and-drops there."""

    REQUIRED_OPTIONS = ("slope", "intercept")
    RECOMMENDED_OPTIONS = ("color", "line_width", "line_style", "alpha", "label")

    def __init__(
        self,
        slope: float,
        intercept: float = 0.0,
        *,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        line_style: str | tuple[float, ...] = "solid",
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        from .curve import check_line_style  # noqa: PLC0415 — shared [D99] guard

        check_alpha(alpha, who="RefLine")
        check_color(color, who="RefLine")
        check_line_style(line_style, who="RefLine")
        self.slope = float(slope)
        self.intercept = float(intercept)
        self.color = color
        self.line_width = line_width
        self.line_style = line_style if isinstance(line_style, str) \
            else tuple(float(v) for v in line_style)
        self.alpha = alpha
        self.label = label
        self._freeze()

    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def lower(self, ctx):
        from ..core.lowering import Lowered  # noqa: PLC0415
        from ..core.marks import Rule  # noqa: PLC0415

        return Lowered(
            marks=(Rule("slope", self._ref_stroke(ctx),
                        at=self.intercept, slope=self.slope),),
            legend=self.legend_entry(ctx.theme, ctx.series_index))


_HEADS = ("end", "both", "none")


class Arrow(_Reference):
    """An arrow between two data points, head at the end point (`head="end"`,
    or `"both"`/`"none"`) — the pointing half of `annotate`; pair with
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
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if head not in _HEADS:
            raise ValidationError(f"Arrow head must be one of {_HEADS}, got {head!r}")
        check_alpha(alpha, who="Arrow")
        check_color(color, who="Arrow")
        self.x0, self.y0 = float(x0), float(y0)
        self.x1, self.y1 = float(x1), float(y1)
        self.head = head
        self.color = color
        self.line_width = line_width
        self.alpha = alpha
        self.label = label
        self._freeze()

    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def lower(self, ctx):
        from ..core.lowering import Lowered, resolve_ref_color  # noqa: PLC0415
        from ..core.marks import ArrowMark, Stroke  # noqa: PLC0415

        stroke = Stroke(resolve_ref_color(self.color, ctx.theme),
                        width=self.line_width, alpha=self.alpha)
        return Lowered(
            marks=(ArrowMark(self.x0, self.y0, self.x1, self.y1, stroke,
                             head=self.head),),
            legend=self.legend_entry(ctx.theme, ctx.series_index))


from .shapes import Ellipse, Polygon, Rect  # noqa: E402 — shapes share the class

ANNOTATION_TYPES: tuple[type, ...] = (HLine, VLine, Span, Text, Arrow,
                                      Rect, Ellipse, Polygon, RefLine)
