"""`Element` — pure declarative plot data (spec §2.1).

Knows its data, channel bindings, options, identity; knows nothing about
rendering. Immutable, value-hashed, Qt-free. Channels bind to **accessors**
(`str | Expression | Callable | ArrayLike`, D14); `channels()` maps each fixed
role to its accessor, and the resolve pipeline turns those into role-keyed
arrays the renderer reads.
"""

from __future__ import annotations

import uuid

from ..data import GriddedRef, TabularRef, accessor_columns
from ._immutable import Immutable

ElementId = str


def _next_element_id() -> ElementId:
    return uuid.uuid4().hex


def require_gridded(ref, *, who: str) -> None:
    if not isinstance(ref, GriddedRef):
        raise TypeError(f"{who} requires gridded (N-D array) data, not tabular")


def validate_channels(data, channels: dict, *, who: str) -> None:
    """Schema-validate the *introspectable* accessors (str / Expression) at
    construction; callables defer to first resolve."""
    if not isinstance(data, TabularRef):
        raise TypeError(f"{who} requires tabular data with named columns")
    have = set(data.schema().names)
    for accessor in channels.values():
        cols = accessor_columns(accessor)
        if cols is None:  # callable — opaque, validated at resolve
            continue
        missing = [c for c in cols if c not in have]
        if missing:
            raise ValueError(
                f"{who}: column(s) {sorted(missing)} not in data; available: {sorted(have)}"
            )


class Element(Immutable):
    REQUIRED_OPTIONS: tuple[str, ...] = ()
    RECOMMENDED_OPTIONS: tuple[str, ...] = ()
    # Fixed channel roles bound to accessors; default role == field name.
    CHANNELS: tuple[str, ...] = ()

    def __init__(self, *, backend_hint: str | None = None, id: ElementId | None = None) -> None:
        self.backend_hint = backend_hint
        self.id = id or _next_element_id()

    def channels(self) -> dict:
        """`{role: accessor}` — what the resolve pipeline materializes into
        role-keyed arrays. Override for non-uniform shapes (e.g. ErrorBars)."""
        return {role: getattr(self, role) for role in self.CHANNELS}

    def _validate_tabular(self) -> None:
        validate_channels(self.data, self.channels(), who=type(self).__name__)

    def _replace_data(self, ref):
        """Low-level copy with `data` swapped (no re-validation) — used by the
        resolve pipeline to install the role-keyed eager ref."""
        obj = object.__new__(type(self))
        for k, v in vars(self).items():
            object.__setattr__(obj, k, v)
        object.__setattr__(obj, "data", ref)
        return obj

    # composition operators — lazy imports avoid an element↔compose cycle
    def __mul__(self, other):
        from .compose import Overlay

        return Overlay((self, other))

    def __add__(self, other):
        from .compose import Layout

        return Layout((self, other))

    def over(self, other):
        return self.__mul__(other)
