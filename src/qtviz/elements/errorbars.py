"""ErrorBars element (spec §5.7)."""

from __future__ import annotations

from typing import Literal

from ..core.color import ColorSpec
from ..core.element import Element, require_tabular_columns
from ..data import as_data_ref


class ErrorBars(Element):
    REQUIRED_OPTIONS = ("x", "y", "err")
    RECOMMENDED_OPTIONS = ("direction", "color")

    def __init__(
        self,
        data,
        *,
        x: str,
        y: str,
        err: str | tuple[str, str],
        direction: Literal["y", "x", "both"] = "y",
        color: ColorSpec | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.err = err if isinstance(err, str) else tuple(err)
        self.direction = direction
        self.color = color
        err_cols = [err] if isinstance(err, str) else list(err)
        require_tabular_columns(self.data, [x, y, *err_cols], who="ErrorBars")
        self._freeze()
