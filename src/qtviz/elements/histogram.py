"""Histogram element (spec §5.6)."""

from __future__ import annotations

from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, as_data_ref


class Histogram(Element):
    REQUIRED_OPTIONS = ("column",)
    RECOMMENDED_OPTIONS = ("bins", "density", "color")
    CHANNELS = ("column",)

    def __init__(
        self,
        data,
        *,
        column: Accessor,
        bins: int | str = "auto",
        density: bool = False,
        color: ColorSpec | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.column = column
        self.bins = bins
        self.density = density
        self.color = color
        self._validate_tabular()
        self._freeze()
