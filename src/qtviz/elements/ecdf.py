"""Ecdf element — the empirical CDF of a column ([D91], parity increment 3)."""

from __future__ import annotations

from ..core._validate import check_alpha
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Ecdf(Element):
    """The empirical cumulative distribution of a raw `column` — a step curve
    rising 0→1. The statistic is computed in core (`_stats.ecdf`, the [D67]
    rule: qtviz decides the numbers) and drawn through each backend's
    post-step curve path."""

    REQUIRED_OPTIONS = ("column",)
    RECOMMENDED_OPTIONS = ("color", "line_width", "alpha", "label")
    CHANNELS = ("column",)

    def __init__(
        self,
        data: DataLike,
        *,
        column: Accessor,
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Ecdf")
        self.data = as_data_ref(data)
        self.column = column
        self.color = color
        self.line_width = line_width
        self.alpha = alpha
        self.label = label
        self._validate_tabular()
        self._freeze()
