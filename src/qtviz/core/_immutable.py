"""`Immutable` — frozen-by-convention mixin (spec §2.1).

Shared by Element, the options containers, Overlay, Layout, Palette. State is set in
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

    - A DataRef (anything exposing a callable `fingerprint`) contributes its
      fingerprint — never its contents.
    - A list is normalized to a tuple.
    - Anything still unhashable (a raw ndarray / DataFrame bound as an
      ArrayLike accessor) falls back to identity, like a buffer fingerprint.
    - Hashable values (str, Expression, a function — identity-hashable) pass
      through, giving value-equality for str/Expression and identity-equality
      for callables (D14).
    """
    fp = getattr(value, "fingerprint", None)
    if callable(fp):
        return fp()
    if isinstance(value, list):
        return tuple(_keyed(v) for v in value)
    try:
        hash(value)
    except TypeError:
        return id(value)
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
        """Class name + only the fields that differ from their constructor
        defaults — `Scatter(data=<tabular x, y>, x='x', y='y')`, not a dump of
        every default plus the auto-generated id. Data refs summarize as their
        cheap schema, never a memory address."""
        import inspect  # noqa: PLC0415
        from collections.abc import Mapping  # noqa: PLC0415

        params: Mapping[str, inspect.Parameter]
        try:
            params = inspect.signature(type(self).__init__).parameters
        except (TypeError, ValueError):  # pragma: no cover — C-level __init__
            params = {}
        parts = []
        for k, v in self._fields().items():
            if k == "id":
                continue  # auto-generated identity — pure noise in a repr
            p = params.get(k)
            if (p is not None and p.default is not inspect.Parameter.empty
                    and _same_as_default(v, p.default)):
                continue
            parts.append(f"{k}={_repr_value(v)}")
        return f"{type(self).__name__}({', '.join(parts)})"


def _same_as_default(value: Any, default: Any) -> bool:
    if value is default:
        return True
    try:
        return bool(value == default)
    except Exception:  # noqa: BLE001 — e.g. ndarray == None ambiguity
        return False


def _repr_value(value: Any) -> str:
    if callable(getattr(value, "fingerprint", None)):  # a data ref
        try:
            sch = value.schema()
            desc = (", ".join(sch.names) if sch.names
                    else "×".join(str(n) for n in sch.shape) if sch.shape else "")
            return f"<{sch.kind}{' ' + desc if desc else ''}>"
        except Exception:  # noqa: BLE001 — a ref that can't schema still reprs
            return f"<{type(value).__name__}>"
    return repr(value)
