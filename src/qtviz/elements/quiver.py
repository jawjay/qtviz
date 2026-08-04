"""Quiver element — vector fields ([D107], roadmap wave 3)."""

from __future__ import annotations

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Quiver(Element):
    """A vector field: arrows at `(x, y)` with components `(u, v)`.
    `arrow_scale` converts (u, v) units to data-space arrow length
    (`"auto"` sizes the largest arrow to ~90% of the field's typical cell);
    `head_scale` scales the barbs. Geometry is computed once in core
    ([D110]) so every backend draws the identical field.

    `key=` adds a reference key ([D112]) — a legend entry whose sample glyph
    is an arrow built by the same core construction as the field, labeled
    with the stated magnitude (`key_label`, e.g. ``key=10,
    key_label="10 m/s"``, or the bare number). Legend-based deliberately:
    qtviz does not model axes-fraction chrome, and the legend is where
    readers look for what a mark means."""

    REQUIRED_OPTIONS = ("x", "y", "u", "v")
    RECOMMENDED_OPTIONS = ("arrow_scale", "head_scale", "color", "line_width",
                           "alpha", "label", "key", "key_label")
    CHANNELS = ("x", "y", "u", "v")
    # [D123]: everything recommended survives lowering — geometry params into
    # the polylines, style into the Stroke, label/key into the legend entry.
    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        u: Accessor,
        v: Accessor,
        arrow_scale: float | str = "auto",
        head_scale: float = 1.0,
        color: ColorSpec | None = None,
        line_width: float = 1.5,  # [D132] uniform default
        alpha: float = 1.0,
        label: str | None = None,
        key: float | None = None,
        key_label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Quiver")
        if isinstance(arrow_scale, str):
            if arrow_scale != "auto":
                raise ValidationError(
                    f"Quiver arrow_scale must be 'auto' or a number, got {arrow_scale!r}")
        elif float(arrow_scale) <= 0:
            raise ValidationError(f"Quiver arrow_scale must be positive, got {arrow_scale!r}")
        if float(head_scale) <= 0:
            raise ValidationError(f"Quiver head_scale must be positive, got {head_scale!r}")
        if key is not None and float(key) <= 0:
            raise ValidationError(f"Quiver key must be a positive magnitude, got {key!r}")
        if key_label is not None and key is None:
            raise ValidationError("Quiver key_label needs key= (the magnitude it names)")
        self.data = as_data_ref(data)
        self.x, self.y, self.u, self.v = x, y, u, v
        self.arrow_scale = arrow_scale if isinstance(arrow_scale, str) else float(arrow_scale)
        self.head_scale = float(head_scale)
        self.color = color
        self.line_width = float(line_width)
        self.alpha = alpha
        self.label = label
        self.key = float(key) if key is not None else None
        self.key_label = key_label
        self._validate_tabular()
        self._freeze()

    def legend_entry(self, theme, index: int = 0):
        """With `key=` set, the entry is the reference key ([D112]): an arrow
        sample glyph plus a label stating the magnitude (`key_label` or the
        number). An element `label` folds in as ``"label (key)"``. Without a
        key this behaves like any labeled element."""
        if self.key is None:
            return super().legend_entry(theme, index)
        from ..core.color import Color  # noqa: PLC0415
        from ..core.encoding import LegendEntry  # noqa: PLC0415

        key_text = self.key_label if self.key_label is not None else f"{self.key:g}"
        label = f"{self.label} ({key_text})" if self.label is not None else key_text
        spec = self.color
        swatch = Color(spec) if spec is not None else theme.palette[index % len(theme.palette)]
        return LegendEntry(label, swatch, glyph="arrow",
                           line_width=self.line_width, head_scale=self.head_scale)

    def lower(self, ctx):
        """[D122] pilot lowering — the whole cross-backend implementation:
        two NaN-separated polylines from the [D107] geometry, style resolved
        into one `Stroke`, legend routed through `legend_entry()`. Not yet on
        the render path: backends still dispatch through their registries
        until wave 2 flips them to draw marks."""
        from ..core.lowering import Lowered, resolve_color  # noqa: PLC0415
        from ..core.marks import Polyline, Stroke  # noqa: PLC0415

        (sx, sy), (hx, hy) = self.resolved_segments()
        stroke = Stroke(resolve_color(self.color, ctx.theme, ctx.series_index),
                        width=self.line_width, alpha=self.alpha)
        return Lowered(
            marks=(Polyline(sx, sy, stroke), Polyline(hx, hy, stroke)),
            legend=self.legend_entry(ctx.theme, ctx.series_index),
        )

    def resolved_segments(self):
        """The shared core geometry from the resolved channels ([D110])."""
        from ..core._geometry import quiver_scale, quiver_segments  # noqa: PLC0415

        d = self.data
        x, y = d.series("x"), d.series("y")
        u, v = d.series("u"), d.series("v")
        scale = (quiver_scale(x, y, u, v) if self.arrow_scale == "auto"
                 else float(self.arrow_scale))
        return quiver_segments(x, y, u, v, scale, self.head_scale)
