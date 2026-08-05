"""Ecdf element — the empirical CDF of a value column (parity increment 3)."""

from __future__ import annotations

from ..core._validate import check_alpha, check_color
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Ecdf(Element):
    """The empirical cumulative distribution of a raw `value` column — a step curve
    rising 0→1. The statistic is computed in core (`_stats.ecdf`, the house
    rule: qtviz decides the numbers) and drawn through each backend's
    post-step curve path."""

    REQUIRED_OPTIONS = ("value",)
    RECOMMENDED_OPTIONS = ("color", "line_width", "alpha", "label", "axis")
    CHANNELS = ("value",)
    HONORED_BY_LOWERING = frozenset(RECOMMENDED_OPTIONS)

    def __init__(
        self,
        data: DataLike,
        *,
        value: Accessor,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        label: str | None = None,
        axis: str = "y",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Ecdf")
        check_color(color, who="Ecdf")
        self.data = as_data_ref(data)
        self.value = value
        self.color = color
        self.line_width = line_width
        self.alpha = alpha
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_axis(axis, "native", who="Ecdf")
        self.label = label
        self.axis = axis
        self._validate_tabular()
        self._freeze()

    def lower(self, ctx):
        """The empirical CDF as one post-step polyline from the shared
        core `ecdf`."""
        from ..core._stats import ecdf  # noqa: PLC0415
        from ..core.lowering import Lowered, resolve_color  # noqa: PLC0415
        from ..core.marks import Polyline, Stroke  # noqa: PLC0415

        xs, fr = ecdf(self.data.series("value"))
        stroke = Stroke(resolve_color(self.color, ctx.theme, ctx.series_index),
                        width=self.line_width, alpha=self.alpha)
        return Lowered(marks=(Polyline(xs, fr, stroke, step="post"),),
                       legend=self.legend_entry(ctx.theme, ctx.series_index))
