"""Histogram element (spec §5.6)."""

from __future__ import annotations

from ..core._stats import BIN_RULES
from ..core._validate import check_alpha, check_color
from ..core.color import ColorSpec
from ..core.element import Element
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class Histogram(Element):
    """Binned frequency of a single raw `value` column. `bins` is a count or one of
    numpy's rule names (`"auto"`, `"fd"`, `"sturges"`, …); the binning is
    computed once in core so every backend draws the same bars ([D93])."""

    REQUIRED_OPTIONS = ("value",)
    RECOMMENDED_OPTIONS = ("bins", "density", "color", "alpha", "label", "axis")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "axis", "bins", "color", "density", "label"})
    CHANNELS = ("value",)

    def __init__(
        self,
        data: DataLike,
        *,
        value: Accessor,
        bins: int | str = "auto",
        density: bool = False,
        color: ColorSpec | None = None,
        alpha: float = 1.0,
        label: str | None = None,
        axis: str = "y",
        backend_hint: str | None = None,
        id=None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        check_alpha(alpha, who="Histogram")
        check_color(color, who="Histogram")
        if isinstance(bins, str):
            if bins not in BIN_RULES:
                raise ValidationError(
                    f"Histogram bins must be an int or one of {BIN_RULES}, got {bins!r}"
                )
        elif not isinstance(bins, int) or isinstance(bins, bool) or bins < 1:
            raise ValidationError(f"Histogram bins must be a positive int, got {bins!r}")
        self.data = as_data_ref(data)
        self.value = value
        self.bins = bins
        self.density = density
        self.color = color
        self.alpha = alpha
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_axis(axis, "native", who="Histogram")
        self.label = label
        self.axis = axis
        self._validate_tabular()
        self._freeze()
