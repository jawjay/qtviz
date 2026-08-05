"""Spread element — filled band between two series (spec §5.8; [D99] adds the
horizontal orientation; [D129] collapses the six optional accessors)."""

from __future__ import annotations

from ..core._validate import check_alpha, check_color
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Spread(Element):
    """A filled band between `lo` and `hi`. Exactly one of `x`/`y` positions
    it: `x=` runs the band in y over x positions (the confidence-interval
    case); `y=` runs it in x over y positions ([D99]). `lo`/`hi` always name
    the band edges."""

    REQUIRED_OPTIONS = ("lo", "hi")
    RECOMMENDED_OPTIONS = ("color", "alpha", "label", "axis")
    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def __init__(
        self,
        data: DataLike,
        *,
        lo: Accessor,
        hi: Accessor,
        x: Accessor | None = None,
        y: Accessor | None = None,
        color: ColorSpec | None = None,
        alpha: float = 0.3,
        label: str | None = None,
        axis: str = "y",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Spread")
        check_color(color, who="Spread")
        if (x is None) == (y is None):
            raise ValidationError(
                "Spread takes exactly one of x= (band in y over x positions) "
                "or y= (band in x over y positions)")
        self.lo, self.hi = lo, hi
        self.x, self.y = x, y
        self.data = as_data_ref(data)
        self.color = color
        self.alpha = alpha
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_axis(axis, "native", who="Spread")
        self.label = label
        self.axis = axis
        self._validate_tabular()
        self._freeze()

    @property
    def orient(self) -> str:
        """Derived, not stored — `with_()` reconstructs from real fields."""
        return "v" if self.x is not None else "h"

    def channels(self) -> dict:
        pos = self.x if self.orient == "v" else self.y
        return {"pos": pos, "lo": self.lo, "hi": self.hi}

    def lower(self, ctx):
        """[D122]: one `Band` mark, either orientation."""
        from ..core.lowering import Lowered, resolve_color  # noqa: PLC0415
        from ..core.marks import Band, Fill  # noqa: PLC0415

        d = self.data
        fill = Fill(resolve_color(self.color, ctx.theme, ctx.series_index),
                    self.alpha)
        mark = Band(d.series("pos"), d.series("lo"), d.series("hi"), fill,
                    orient=self.orient)
        return Lowered(marks=(mark,),
                       legend=self.legend_entry(ctx.theme, ctx.series_index))
