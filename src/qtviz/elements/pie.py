"""Pie element — proportional wedges ([D90], parity increment 3)."""

from __future__ import annotations

from ..core._validate import check_alpha
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Pie(Element):
    """Proportional wedges of a non-negative `value` column, optionally
    labeled by a `by` category column; `hole` (0 ≤ hole < 1) makes a donut. Slice
    colors cycle the theme palette in row order.

    Supported on matplotlib and webengine ([D90]); pyqtgraph has no pie
    primitive, so negotiation routes around it (the `RawFigure` precedent —
    an element need not render everywhere)."""

    REQUIRED_OPTIONS = ("value",)
    RECOMMENDED_OPTIONS = ("by", "hole", "alpha")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "by", "hole"})

    def __init__(
        self,
        data: DataLike,
        *,
        value: Accessor,
        by: Accessor | None = None,
        hole: float = 0.0,
        alpha: float = 1.0,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if not 0.0 <= float(hole) < 1.0:
            raise ValidationError(f"Pie hole must be in [0, 1), got {hole!r}")
        check_alpha(alpha, who="Pie")
        self.data = as_data_ref(data)
        self.value = value
        self.by = by
        self.hole = float(hole)
        self.alpha = alpha
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"value": self.value}
        if self.by is not None:
            ch["by"] = self.by
        return ch
