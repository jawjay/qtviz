"""`Element` — pure declarative plot data (spec §2.1).

Knows its data, mapping, options, identity; knows nothing about rendering.
Immutable, value-hashed, Qt-free. Subclasses set state in `__init__` and call
`self._freeze()` last. Field names are validated against the data's schema at
construction (§6.1) so a typo'd column fails early.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from ..data import GriddedRef, TabularRef
from ._immutable import Immutable

ElementId = str


def _next_element_id() -> ElementId:
    return uuid.uuid4().hex


def require_tabular_columns(ref, names: Sequence[str | None], *, who: str) -> None:
    """Validate that `names` exist as columns on a tabular ref."""
    if not isinstance(ref, TabularRef):
        raise TypeError(f"{who} requires tabular data with named columns")
    have = set(ref.schema().names)
    missing = [n for n in names if n is not None and n not in have]
    if missing:
        raise ValueError(
            f"{who}: column(s) {missing} not in data; available: {sorted(have)}"
        )


def require_gridded(ref, *, who: str) -> None:
    if not isinstance(ref, GriddedRef):
        raise TypeError(f"{who} requires gridded (N-D array) data, not tabular")


class Element(Immutable):
    REQUIRED_OPTIONS: tuple[str, ...] = ()
    RECOMMENDED_OPTIONS: tuple[str, ...] = ()

    def __init__(self, *, backend_hint: str | None = None, id: ElementId | None = None) -> None:
        self.backend_hint = backend_hint
        self.id = id or _next_element_id()

    # composition operators — lazy imports avoid an element↔compose cycle
    def __mul__(self, other):
        from .compose import Overlay

        return Overlay((self, other))

    def __add__(self, other):
        from .compose import Layout

        return Layout((self, other))

    def over(self, other):
        return self.__mul__(other)
