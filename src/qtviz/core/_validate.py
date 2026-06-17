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


def check_exclusive(static, by, *, names: tuple[str, str], who: str) -> None:
    """Reject binding the same channel both statically and to a column —
    e.g. `color=` (static) and `color_by=` (column) at once."""
    if static is not None and by is not None:
        raise ValidationError(
            f"{who}: pass {names[0]} (static) or {names[1]} (column), not both"
        )
