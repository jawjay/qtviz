"""Spread element — filled band between two series (spec §5.8; [D99] adds the
horizontal orientation)."""

from __future__ import annotations

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Spread(Element):
    """A filled band: vertical — `y_lo`/`y_hi` over `x` (e.g. a confidence
    interval) — or horizontal — `x_lo`/`x_hi` over `y` ([D99]). Pass exactly
    one complete set; `orient` is derived (`"v"` or `"h"`)."""

    REQUIRED_OPTIONS = ("x", "y_lo", "y_hi")
    RECOMMENDED_OPTIONS = ("color", "alpha", "label")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor | None = None,
        y_lo: Accessor | None = None,
        y_hi: Accessor | None = None,
        y: Accessor | None = None,
        x_lo: Accessor | None = None,
        x_hi: Accessor | None = None,
        color: ColorSpec | None = None,
        alpha: float = 0.3,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Spread")
        v = (x, y_lo, y_hi)
        h = (y, x_lo, x_hi)
        if any(a is not None for a in v) and any(a is not None for a in h):
            raise ValidationError(
                "Spread takes either (x, y_lo, y_hi) or (y, x_lo, x_hi), not a mix"
            )
        if not (all(a is not None for a in v) or all(a is not None for a in h)):
            raise ValidationError(
                "Spread requires all of (x, y_lo, y_hi) or all of (y, x_lo, x_hi)"
            )
        self.data = as_data_ref(data)
        self.x, self.y_lo, self.y_hi = x, y_lo, y_hi
        self.y, self.x_lo, self.x_hi = y, x_lo, x_hi
        self.color = color
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()

    @property
    def orient(self) -> str:
        """Derived, not stored — `with_()` reconstructs from real fields."""
        return "v" if self.x is not None else "h"

    def channels(self) -> dict:
        if self.orient == "v":
            return {"x": self.x, "y_lo": self.y_lo, "y_hi": self.y_hi}
        return {"y": self.y, "x_lo": self.x_lo, "x_hi": self.x_hi}
