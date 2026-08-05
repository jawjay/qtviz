"""The shared raster-norm surface: `norm` (string shorthand | `Norm`) +
`clim` — replaces the per-element 5-parameter cluster. The old field names
survive as read-only properties so the pipeline reads one vocabulary.
"""

from __future__ import annotations

from ..core.encoding import Norm
from ..errors import ValidationError


def check_norm_clim(norm, clim, *, who: str):
    """Validate + canonicalize → `(norm_as_given, clim_tuple | None)`.
    `Norm(...)` validates its own parameters; the cross checks left are the
    clim pair and log positivity."""
    spec = Norm(norm) if isinstance(norm, str) else norm
    if not isinstance(spec, Norm):
        raise ValidationError(
            f"{who} norm must be a norm name or a Norm spec, got {norm!r}")
    if clim is not None:
        lo, hi = clim
        if lo is not None and hi is not None and not float(lo) < float(hi):
            raise ValidationError(f"{who}: clim must be (lo, hi) with lo < hi, got {clim!r}")
        if spec.kind == "log" and lo is not None and float(lo) <= 0:
            raise ValidationError(f"{who}: norm='log' requires a positive clim lo")
        clim = (float(lo) if lo is not None else None,
                float(hi) if hi is not None else None)
    return norm, clim


class NormedRaster:
    """Mixin: derived read-only views of (`norm`, `clim`) under the
    normalization pipeline's vocabulary. The host element sets both attrs."""

    norm: str | Norm
    clim: tuple | None

    @property
    def norm_spec(self) -> Norm:
        return self.norm if isinstance(self.norm, Norm) else Norm(self.norm)

    @property
    def norm_kind(self) -> str:
        return self.norm.kind if isinstance(self.norm, Norm) else self.norm

    @property
    def vmin(self):
        return self.clim[0] if self.clim is not None else None

    @property
    def vmax(self):
        return self.clim[1] if self.clim is not None else None

    @property
    def gamma(self) -> float:
        return self.norm_spec.gamma

    @property
    def linthresh(self) -> float:
        return self.norm_spec.linthresh

    @property
    def norm_levels(self):
        return self.norm_spec.levels
