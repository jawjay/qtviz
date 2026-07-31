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
    ([D110]) so every backend draws the identical field."""

    REQUIRED_OPTIONS = ("x", "y", "u", "v")
    RECOMMENDED_OPTIONS = ("arrow_scale", "head_scale", "color", "line_width",
                           "alpha", "label")
    CHANNELS = ("x", "y", "u", "v")

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
        line_width: float = 1.0,
        alpha: float = 1.0,
        label: str | None = None,
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
        self.data = as_data_ref(data)
        self.x, self.y, self.u, self.v = x, y, u, v
        self.arrow_scale = arrow_scale if isinstance(arrow_scale, str) else float(arrow_scale)
        self.head_scale = float(head_scale)
        self.color = color
        self.line_width = float(line_width)
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()

    def resolved_segments(self):
        """The shared core geometry from the resolved channels ([D110])."""
        from ..core._geometry import quiver_scale, quiver_segments  # noqa: PLC0415

        d = self.data
        x, y = d.series("x"), d.series("y")
        u, v = d.series("u"), d.series("v")
        scale = (quiver_scale(x, y, u, v) if self.arrow_scale == "auto"
                 else float(self.arrow_scale))
        return quiver_segments(x, y, u, v, scale, self.head_scale)
