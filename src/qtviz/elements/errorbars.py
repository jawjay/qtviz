"""ErrorBars element (spec §5.7; limit arrows , wave 1.4)."""

from __future__ import annotations

from typing import Literal

import numpy as np

from ..core.color import ColorSpec
from ..core.element import Element, ElementId
from ..data import Accessor, DataLike, as_data_ref
from ..errors import ValidationError


class ErrorBars(Element):
    """Error bars around `y` — `err` is symmetric, or `(lo, hi)` for asymmetric.

    `lo_limit=` / `hi_limit=` name optional boolean columns; where
    true, that side's cap is drawn as an outward arrowhead — "the true value
    lies beyond" (mpl's lolims/uplims semantic). Heads reuse the shared
    quiver construction and refer to the `direction` axis, so limits are
    per-axis (`direction="both"` rejects them — use two elements)."""

    REQUIRED_OPTIONS = ("x", "y", "err")
    RECOMMENDED_OPTIONS = ("direction", "color", "label", "lo_limit", "hi_limit")
    # [D123] wave-4: the honored set shared by every native renderer;
    # backends subtract their declared deltas (HONORED_DELTAS).
    HONORED_NATIVE = frozenset({"alpha", "axis", "color", "direction", "hi_limit",
                                "label", "line_width", "lo_limit"})

    def __init__(
        self,
        data: DataLike,
        *,
        x: Accessor,
        y: Accessor,
        err: Accessor | tuple[Accessor, Accessor],
        direction: Literal["y", "x", "both"] = "y",
        color: ColorSpec | None = None,
        line_width: float = 1.5,
        alpha: float = 1.0,
        label: str | None = None,
        axis: str = "y",
        lo_limit: Accessor | None = None,
        hi_limit: Accessor | None = None,
        backend_hint: str | None = None,
        id: ElementId | None = None,
    ) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        if direction == "both" and (lo_limit is not None or hi_limit is not None):
            raise ValidationError(
                "ErrorBars: lo_limit/hi_limit are per-axis (they follow "
                "direction) — use direction='x' or 'y', or two elements")
        self.data = as_data_ref(data)
        self.x, self.y = x, y
        self.err = err
        self.direction = direction
        from ..core._validate import check_alpha, check_color  # noqa: PLC0415
        from .curve import check_axis  # noqa: PLC0415 — shared [D88] guard

        check_alpha(alpha, who="ErrorBars")
        check_color(color, who="ErrorBars")
        check_axis(axis, "native", who="ErrorBars")
        self.color = color
        self.line_width = float(line_width)
        self.alpha = float(alpha)
        self.axis = axis
        self.label = label
        self.lo_limit = lo_limit
        self.hi_limit = hi_limit
        self._validate_tabular()
        self._freeze()

    def channels(self) -> dict:
        ch = {"x": self.x, "y": self.y}
        if isinstance(self.err, tuple):  # (lo, hi) accessors
            ch["err_lo"], ch["err_hi"] = self.err
        else:  # single accessor → symmetric
            ch["err_lo"] = ch["err_hi"] = self.err
        if self.lo_limit is not None:
            ch["lo_limit"] = self.lo_limit
        if self.hi_limit is not None:
            ch["hi_limit"] = self.hi_limit
        return ch

    def resolved_limits(self):
        """`(err_lo, err_hi, arrows)` from the resolved channels:
        limited sides are zeroed (the arrow shaft replaces the bar) and
        `arrows` is the core `(shaft, head)` polyline pair — `None` when no
        limit columns are set, so plain error bars render exactly as before."""
        from ..core._geometry import limit_arrow_segments  # noqa: PLC0415
        from ..core._time import as_float_seconds  # noqa: PLC0415

        d = self.data
        lo = np.asarray(d.series("err_lo"), dtype="float64")
        hi = np.asarray(d.series("err_hi"), dtype="float64")
        if self.lo_limit is None and self.hi_limit is None:
            return lo, hi, None
        lo_m = (np.asarray(d.series("lo_limit"), dtype=bool)
                if self.lo_limit is not None else None)
        hi_m = (np.asarray(d.series("hi_limit"), dtype=bool)
                if self.hi_limit is not None else None)
        arrows = limit_arrow_segments(
            as_float_seconds(d.series("x")), as_float_seconds(d.series("y")),
            lo, hi, lo_m, hi_m, direction=self.direction)
        if lo_m is not None:
            lo = np.where(lo_m, 0.0, lo)
        if hi_m is not None:
            hi = np.where(hi_m, 0.0, hi)
        return lo, hi, arrows
