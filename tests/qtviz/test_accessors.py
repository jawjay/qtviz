"""Tier-1 — functional data binding via accessors (D14).

A channel is an Accessor (str | Expression | Callable | ArrayLike) resolved
against the data object. `str` is sugar for `col(name)`; `Expression` is the
serializable/introspectable derived form; `Callable` is the escape hatch;
`ArrayLike` is literal values.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
data = pytest.importorskip("qtviz.data")

pytestmark = pytest.mark.tier1


@pytest.fixture
def t():
    return {"a": np.arange(5.0), "b": np.arange(5.0) * 10, "y": np.arange(5.0) ** 2}


# ── Expression AST ───────────────────────────────────────────────────────────
def test_expression_resolves(t):
    e = qv.col("a") + qv.col("b")
    np.testing.assert_array_equal(e.resolve(t), t["a"] + t["b"])


def test_expression_columns_introspection():
    assert (qv.col("a") + qv.col("b") * 2).columns() == {"a", "b"}
    assert qv.col("x").log().columns() == {"x"}


def test_expression_serializes_round_trip():
    e = (qv.col("a") - qv.col("b")).log()
    assert data.expr.from_dict(e.to_dict()) == e


def test_expression_value_equal_and_hashable():
    assert (qv.col("a") + qv.col("b")) == (qv.col("a") + qv.col("b"))
    assert hash(qv.col("a") + 1) == hash(qv.col("a") + 1)
    assert (qv.col("a") + qv.col("b")) != (qv.col("a") + qv.col("c"))


def test_expression_predicate_and_transform(t):
    pred = (qv.col("a") >= 1) & (qv.col("a") <= 3)
    np.testing.assert_array_equal(pred.resolve(t), (t["a"] >= 1) & (t["a"] <= 3))
    np.testing.assert_allclose(qv.col("b").sqrt().resolve(t), np.sqrt(t["b"]))


# ── resolve_channels over the four accessor kinds ────────────────────────────
def test_resolve_channels_all_kinds_agree(t):
    ref = data.as_data_ref(t)
    expected = t["a"] + t["b"]
    out_str = ref.resolve_channels({"x": "a"})["x"]
    out_expr = ref.resolve_channels({"x": qv.col("a") + qv.col("b")})["x"]
    out_call = ref.resolve_channels({"x": lambda d: d["a"] + d["b"]})["x"]
    out_arr = ref.resolve_channels({"x": expected})["x"]
    np.testing.assert_array_equal(out_str, t["a"])
    np.testing.assert_array_equal(out_expr, expected)
    np.testing.assert_array_equal(out_call, expected)
    np.testing.assert_array_equal(out_arr, expected)


def test_resolve_channels_length_mismatch_raises(t):
    ref = data.as_data_ref(t)
    with pytest.raises(ValueError):
        ref.resolve_channels({"x": "a", "y": np.arange(3)})  # 5 vs 3


# ── Element binding ──────────────────────────────────────────────────────────
def test_element_accepts_every_accessor_kind(t):
    qv.Scatter(t, x="a", y="y")
    qv.Scatter(t, x=qv.col("a") + qv.col("b"), y="y")
    qv.Scatter(t, x=lambda d: d["a"] * 2, y="y")
    qv.Scatter(t, x=np.linspace(0, 1, 5), y="y")


def test_channels_reports_roles(t):
    s = qv.Scatter(t, x="a", y="y")
    assert set(s.channels()) == {"x", "y"}
    eb = qv.ErrorBars(t, x="a", y="y", err="b")
    assert set(eb.channels()) == {"x", "y", "err_lo", "err_hi"}  # symmetric err normalized


def test_resolve_node_keys_by_role(t):
    s = qv.Scatter(t, x=qv.col("a") + qv.col("b"), y="y")
    resolved = data.resolve_node(s)
    np.testing.assert_array_equal(resolved.data.series("x"), t["a"] + t["b"])
    np.testing.assert_array_equal(resolved.data.series("y"), t["y"])


def test_str_and_expression_validate_early_callable_defers(t):
    with pytest.raises(ValueError):
        qv.Scatter(t, x="nope", y="y")
    with pytest.raises(ValueError):
        qv.Scatter(t, x=qv.col("nope") + 1, y="y")
    qv.Scatter(t, x=lambda d: d["nope"], y="y")  # callable opaque → no early error


def test_expression_bound_element_is_value_equal(t):
    a = qv.Scatter(t, x=qv.col("a") + qv.col("b"), y="y")
    b = qv.Scatter(t, x=qv.col("a") + qv.col("b"), y="y")
    assert a == b and hash(a) == hash(b)


def test_array_bound_element_is_hashable(t):
    hash(qv.Scatter(t, x=np.linspace(0, 1, 5), y="y"))  # must not raise
