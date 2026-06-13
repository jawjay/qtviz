"""`Immutable` — frozen-by-convention mixin (spec §2.1).

Shared by Element, Options, Overlay, Layout, Palette. State is set in
`__init__`; subclasses call `self._freeze()` at the end to lock it. Mutations
return new instances via `.with_()`.

Value identity (`__eq__`/`__hash__`) deliberately **excludes `id`** and
represents data refs by their cheap `fingerprint()` rather than their
contents — that is what keeps array/DataFrame-backed types hashable and lets
two equally-configured objects compare equal (resolved Q-G).
"""

from __future__ import annotations

from typing import Any


def _keyed(value: Any) -> Any:
    """Map a field value to something cheap and hashable for the value-key.

    A DataRef (anything exposing a callable `fingerprint`) contributes its
    fingerprint — never its contents, which may be an unhashable numpy buffer.
    Everything else must already be hashable (scalars, tuples, nested
    Immutables); a list is normalized to a tuple as a convenience.
    """
    fp = getattr(value, "fingerprint", None)
    if callable(fp):
        return fp()
    if isinstance(value, list):
        return tuple(value)
    return value


class Immutable:
    _frozen = False

    def _freeze(self) -> None:
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, key: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(
                f"{type(self).__name__} is immutable; use .with_({key}=...)"
            )
        object.__setattr__(self, key, value)

    def __delattr__(self, key: str) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(f"{type(self).__name__} is immutable")
        object.__delattr__(self, key)

    def _fields(self) -> dict[str, Any]:
        """Public attrs (non-underscore). Drives `.with_()` and `__repr__`.

        Contract: every key here must be a constructor keyword, so that
        `type(self)(**self._fields())` reconstructs an equal instance. The
        round-trip is asserted by the conformance tests.
        """
        return {k: v for k, v in vars(self).items() if not k.startswith("_")}

    def with_(self, **changes: Any):
        """Copy-on-write update. Preserves `id` unless overridden in `changes`."""
        fields = self._fields()
        fields.update(changes)
        return type(self)(**fields)

    def _value_key(self) -> tuple:
        items = tuple(
            (k, _keyed(v))
            for k, v in sorted(self._fields().items())
            if k != "id"
        )
        return (type(self), items)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Immutable)
            and type(self) is type(other)
            and self._value_key() == other._value_key()
        )

    def __hash__(self) -> int:
        return hash(self._value_key())

    def __repr__(self) -> str:
        inner = ", ".join(f"{k}={v!r}" for k, v in self._fields().items())
        return f"{type(self).__name__}({inner})"
