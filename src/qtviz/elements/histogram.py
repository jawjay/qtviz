"""Histogram element (spec §5.6)."""

from __future__ import annotations

from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref


class Histogram(Element):
    """Binned frequency of a single raw `column`."""

    REQUIRED_OPTIONS = ("column",)
    RECOMMENDED_OPTIONS = ("bins", "density", "color", "label")
    CHANNELS = ("column",)

    def __init__(
        self,
        data: DataLike,
        *,
        column: Accessor,
        bins: int | str = "auto",
        density: bool = False,
        color: ColorSpec | None = None,
        label: str | None = None,
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.data = as_data_ref(data)
        self.column = column
        self.bins = bins
        self.density = density
        self.color = color
        self.label = label
        self._validate_tabular()
        self._freeze()
