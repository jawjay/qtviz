"""ErrorBars element (spec §5.7)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class ErrorBars(Element):
    """Error bars around `y` — `err` is symmetric, or `(lo, hi)` for asymmetric."""

    REQUIRED_OPTIONS = ("x", "y", "err")
    RECOMMENDED_OPTIONS = ("direction", "color", "label")

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        err: Accessor | tuple[Accessor, Accessor],
        direction: Literal["y", "x", "both"] = "y",
        color: ColorSpec | None = None,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.err = err
        self.direction = direction
        self.color = color
        self.label = label
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"x": self.x, "y": self.y}
        if isinstance(self.err, tuple):  # (lo, hi) accessors
            ch["err_lo"], ch["err_hi"] = self.err
        else:  # single accessor → symmetric
            ch["err_lo"] = ch["err_hi"] = self.err
        return ch
