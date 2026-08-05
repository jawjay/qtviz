"""Shared construction-time validators.

One place for the small checks every Element / Options constructor repeats, so
the rule (and its message) stays identical as new elements are added. All raise
`ValidationError` (a `QtvizError` *and* a `ValueError`), keeping rejection of
bad input uniform across the public surface.
"""

from __future__ import annotations

from ..errors import ValidationError


def check_alpha(alpha: float | None, *, who: str) -> None:
    """Reject an opacity outside the closed unit interval."""
    if alpha is not None and not (0.0 <= alpha <= 1.0):
        raise ValidationError(f"{who}: alpha must be in [0, 1], got {alpha}")


def check_choice(value, choices, *, who: str, param: str, none_ok: bool = False) -> None:
    """Reject a value outside a fixed vocabulary — the shared check behind every
    `Literal[...]` constructor parameter, so a typo fails at construction with
    the allowed set in the message, never as a backend `KeyError` at render."""
    if value is None and none_ok:
        return
    if value not in choices:
        suffix = " or None" if none_ok else ""
        raise ValidationError(
            f"{who}: {param} must be one of {tuple(choices)}{suffix}, got {value!r}"
        )


def check_color(color, *, who: str) -> None:
    """Validate a static `color=` eagerly at construction ([D143]): a bad name
    or malformed tuple fails here, at the call the user wrote, not at render."""
    if color is not None:
        from .color import Color  # noqa: PLC0415 — avoid an import cycle at module load

        Color(color)


def check_exclusive(static, by, *, names: tuple[str, str], who: str) -> None:
    """Reject binding the same channel both statically and to a column —
    e.g. `color=` (static) and `color_by=` (column) at once."""
    if static is not None and by is not None:
        raise ValidationError(
            f"{who}: pass {names[0]} (static) or {names[1]} (column), not both"
        )


_VALUE_AGGS = ("sum", "mean", "max", "min", "std")


def check_agg(agg: str, color_by, raster: str, *, who: str) -> None:
    """Validate the `(agg, color_by, raster)` triple for a rasterizable element
    ([D49]). `agg` is the per-pixel Datashader reduction, so it only applies under
    `raster="datashader"/"auto"`; a value reduction (sum/mean/max/min/std) or a
    categorical `by` needs a `color_by` column to reduce."""
    if agg == "auto":
        return
    if raster == "native":
        raise ValidationError(
            f"{who}: agg={agg!r} needs raster='datashader' or 'auto' "
            "(native rendering does not aggregate per pixel)"
        )
    if agg in _VALUE_AGGS and color_by is None:
        raise ValidationError(f"{who}: agg={agg!r} needs color_by (the column to aggregate)")
    if agg == "by" and color_by is None:
        raise ValidationError(f"{who}: agg='by' needs a categorical color_by column")
