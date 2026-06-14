"""ErrorBars element (spec §5.7)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, as_data_ref


class ErrorBars(Element):
    REQUIRED_OPTIONS = ("x", "y", "err")
    RECOMMENDED_OPTIONS = ("direction", "color")

    def __init__(
        self,
        data,
        *,
        x: Accessor,
        y: Accessor,
        err: Accessor | tuple[Accessor, Accessor],
        direction: Literal["y", "x", "both"] = "y",
        color: ColorSpec | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.err = err
        self.direction = direction
        self.color = color
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"x": self.x, "y": self.y}
        if isinstance(self.err, tuple):  # (lo, hi) accessors
            ch["err_lo"], ch["err_hi"] = self.err
        else:  # single accessor → symmetric
            ch["err_lo"] = ch["err_hi"] = self.err
        return ch
