"""Accessors — how a channel's values are extracted from the data (D14).

`Accessor = str | Expression | Callable | ArrayLike`. A string column name is the
trivial case (`col(name)`); an `Expression` is the preferred derived/serializable
form; a `Callable[[data], col]` is the escape hatch for arbitrary Python; an
`ArrayLike` is literal values.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Union

import numpy as np

from .expr import Expr

Accessor = Union[str, Expr, Callable[[Any], Any], "np.typing.ArrayLike"]


def accessor_columns(accessor: Accessor) -> set[str] | None:
    """Statically-referenced column names, or `None` when not introspectable
    (a `Callable` is opaque). Used for schema validation + explicit pushdown."""
    if isinstance(accessor, str):
        return {accessor}
    if isinstance(accessor, Expr):
        return accessor.columns()
    if callable(accessor):
        return None
    return set()  # array literal — no columns


def resolve_accessor(accessor: Accessor, *, columns: dict, native: Any) -> np.ndarray:
    """Resolve one accessor to a numpy array.

    - `str` / `Expression` resolve against `columns` (a name → array namespace;
      numpy for eager refs), so the operators/ufuncs compose uniformly.
    - `Callable` is applied to `native` (the real container) so the user's code
      gets full container methods.
    - `ArrayLike` is taken as-is.
    """
    if isinstance(accessor, str):
        return np.asarray(columns[accessor])
    if isinstance(accessor, Expr):
        return np.asarray(accessor.resolve(columns))
    if callable(accessor):
        return np.asarray(accessor(native))
    return np.asarray(accessor)
