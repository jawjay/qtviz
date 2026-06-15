"""`Expression` — a serializable, introspectable, lazy column expression (D14).

A qtviz-owned AST with operator overloading: `col("a") + col("b")`,
`col("pop").log()`, `(col("x") >= 0) & (col("y") < 10)`. It is the preferred
accessor for anything derived because, unlike a `Callable`, it keeps every
static property a string column name has:

- **serializable** — `to_dict()` / `from_dict()` round-trip (Studio project files)
- **introspectable** — `columns()` walks the AST for referenced column names
  (schema validation + explicit pushdown)
- **value-equal** — immutable value (works in Element identity/hashing)
- **lazy** — `resolve(namespace)` compiles to operations on the data: arithmetic
  / comparison / boolean via Python operators (lazy on dask/polars, eager on
  pandas/numpy); transforms via numpy ufuncs.

`resolve(namespace)` evaluates against a mapping `name -> column` (numpy arrays
for eager refs, or the native lazy frame for lazy refs — both support
`getitem` + the operators/ufuncs used here).
"""

from __future__ import annotations

from typing import Any

import numpy as np

# numpy ufuncs dispatch to dask/pandas via the array protocol, so these stay
# lazy on dask and eager on numpy/pandas.
_FUNCS = {
    "log": np.log,
    "log10": np.log10,
    "abs": np.abs,
    "sqrt": np.sqrt,
    "exp": np.exp,
    "negative": np.negative,
}


def _lift(value: Any) -> Expr:
    return value if isinstance(value, Expr) else Lit(value)


class Expr:
    """Base expression node. Immutable; value-equal by its serialized form."""

    def resolve(self, namespace) -> Any:
        raise NotImplementedError

    def columns(self) -> set[str]:
        """Referenced column names (empty if none)."""
        return set()

    def to_dict(self) -> dict:
        raise NotImplementedError

    # ── operator overloading → derived expressions ──
    def __add__(self, o): return BinOp("add", self, _lift(o))
    def __radd__(self, o): return BinOp("add", _lift(o), self)
    def __sub__(self, o): return BinOp("sub", self, _lift(o))
    def __rsub__(self, o): return BinOp("sub", _lift(o), self)
    def __mul__(self, o): return BinOp("mul", self, _lift(o))
    def __rmul__(self, o): return BinOp("mul", _lift(o), self)
    def __truediv__(self, o): return BinOp("div", self, _lift(o))
    def __rtruediv__(self, o): return BinOp("div", _lift(o), self)
    def __neg__(self): return Func("negative", self)

    def __gt__(self, o): return BinOp("gt", self, _lift(o))
    def __ge__(self, o): return BinOp("ge", self, _lift(o))
    def __lt__(self, o): return BinOp("lt", self, _lift(o))
    def __le__(self, o): return BinOp("le", self, _lift(o))
    def __and__(self, o): return BinOp("and", self, _lift(o))
    def __or__(self, o): return BinOp("or", self, _lift(o))

    # transforms
    def log(self): return Func("log", self)
    def log10(self): return Func("log10", self)
    def abs(self): return Func("abs", self)
    def sqrt(self): return Func("sqrt", self)
    def exp(self): return Func("exp", self)

    def clip(self, lo=None, hi=None): return Clip(self, lo, hi)

    # value identity via serialized form (so equal exprs are == and hashable)
    def _key(self):
        return _freeze(self.to_dict())

    def __eq__(self, other) -> bool:
        return isinstance(other, Expr) and self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __repr__(self) -> str:
        return f"Expr({self.to_dict()!r})"


class Col(Expr):
    def __init__(self, name: str) -> None:
        self.name = name

    def resolve(self, namespace):
        return namespace[self.name]

    def columns(self) -> set[str]:
        return {self.name}

    def to_dict(self) -> dict:
        return {"k": "col", "name": self.name}


class Lit(Expr):
    def __init__(self, value) -> None:
        self.value = value

    def resolve(self, namespace):
        return self.value

    def to_dict(self) -> dict:
        return {"k": "lit", "value": self.value}


_BINOPS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "and": lambda a, b: a & b,
    "or": lambda a, b: a | b,
}


class BinOp(Expr):
    def __init__(self, op: str, left: Expr, right: Expr) -> None:
        self.op = op
        self.left = left
        self.right = right

    def resolve(self, namespace):
        return _BINOPS[self.op](self.left.resolve(namespace), self.right.resolve(namespace))

    def columns(self) -> set[str]:
        return self.left.columns() | self.right.columns()

    def to_dict(self) -> dict:
        return {"k": "binop", "op": self.op, "left": self.left.to_dict(),
                "right": self.right.to_dict()}


class Func(Expr):
    def __init__(self, name: str, arg: Expr) -> None:
        self.name = name
        self.arg = arg

    def resolve(self, namespace):
        return _FUNCS[self.name](self.arg.resolve(namespace))

    def columns(self) -> set[str]:
        return self.arg.columns()

    def to_dict(self) -> dict:
        return {"k": "func", "name": self.name, "arg": self.arg.to_dict()}


class Clip(Expr):
    def __init__(self, arg: Expr, lo, hi) -> None:
        self.arg = arg
        self.lo = lo
        self.hi = hi

    def resolve(self, namespace):
        return np.clip(self.arg.resolve(namespace), self.lo, self.hi)

    def columns(self) -> set[str]:
        return self.arg.columns()

    def to_dict(self) -> dict:
        return {"k": "clip", "arg": self.arg.to_dict(), "lo": self.lo, "hi": self.hi}


def col(name: str) -> Col:
    """Reference a data column by name in an `Expression` (e.g. `col("a") - col("b")`)."""
    return Col(name)


def lit(value) -> Lit:
    """A literal scalar inside an `Expression` (broadcast against the columns)."""
    return Lit(value)


def from_dict(d: dict) -> Expr:
    k = d["k"]
    if k == "col":
        return Col(d["name"])
    if k == "lit":
        return Lit(d["value"])
    if k == "binop":
        return BinOp(d["op"], from_dict(d["left"]), from_dict(d["right"]))
    if k == "func":
        return Func(d["name"], from_dict(d["arg"]))
    if k == "clip":
        return Clip(from_dict(d["arg"]), d["lo"], d["hi"])
    raise ValueError(f"unknown expression node {k!r}")


def _freeze(obj):
    if isinstance(obj, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in obj.items()))
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    return obj
