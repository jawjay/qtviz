"""Histogram element (spec §5.6)."""

from __future__ import annotations

from ..core._stats import BIN_RULES
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Histogram(Element):
    """Binned frequency of a single raw `column`. `bins` is a count or one of
    numpy's rule names (`"auto"`, `"fd"`, `"sturges"`, …); the binning is
    computed once in core so every backend draws the same bars ([D93])."""

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
        if isinstance(bins, str):
            if bins not in BIN_RULES:
                raise ValidationError(
                    f"Histogram bins must be an int or one of {BIN_RULES}, got {bins!r}"
                )
        elif not isinstance(bins, int) or isinstance(bins, bool) or bins < 1:
            raise ValidationError(f"Histogram bins must be a positive int, got {bins!r}")
        self.data = as_data_ref(data)
        self.column = column
        self.bins = bins
        self.density = density
        self.color = color
        self.label = label
        self._validate_tabular()
        self._freeze()
