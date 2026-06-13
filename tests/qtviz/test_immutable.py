"""Tier-1 — the Immutable contract (spec §2.1).

Value identity excludes `id` and fingerprints data refs; this is what makes
two equally-configured Elements compare equal and hash alike (resolved Q-G),
which the negotiation cache and the `old_root == new_root` render
short-circuit rely on. Array/DataFrame-backed Elements must stay hashable —
the bug this guards against is `hash()` raising on a numpy buffer.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1


def test_frozen_after_construction(table):
    s = qv.Scatter(table, x="x", y="y")
    with pytest.raises(AttributeError):
        s.alpha = 0.5  # type: ignore[misc]


def test_with_returns_new_instance_original_unchanged(table):
    s = qv.Scatter(table, x="x", y="y", alpha=1.0)
    s2 = s.with_(alpha=0.5)
    assert s2 is not s
    assert s2.alpha == 0.5
    assert s.alpha == 1.0  # copy-on-write; original untouched


def test_with_no_change_is_equal_but_distinct(table):
    s = qv.Scatter(table, x="x", y="y")
    assert s.with_() == s
    assert s.with_() is not s


def test_with_preserves_id(table):
    s = qv.Scatter(table, x="x", y="y")
    assert s.with_(alpha=0.3).id == s.id  # stable identity across edits (Q-P)


def test_value_equality_excludes_id(table):
    # Two independently constructed Elements over the SAME data object are
    # value-equal even though their auto-generated ids differ.
    a = qv.Scatter(table, x="x", y="y")
    b = qv.Scatter(table, x="x", y="y")
    assert a.id != b.id
    assert a == b


def test_hashable_with_array_data(table):
    a = qv.Scatter(table, x="x", y="y")
    b = qv.Scatter(table, x="x", y="y")
    # Must not raise on the numpy buffers, and equal objects hash alike.
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_distinct_data_objects_are_not_equal(table):
    # Fingerprint identity means "same data object", not deep value compare.
    other = {k: v.copy() for k, v in table.items()}
    assert qv.Scatter(table, x="x", y="y") != qv.Scatter(other, x="x", y="y")


def test_equality_does_not_raise_on_dataframe(table):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(table)
    a = qv.Scatter(df, x="x", y="y")
    b = qv.Scatter(df, x="x", y="y")
    assert isinstance(a == b, bool)  # never an elementwise DataFrame truth-value
    assert hash(a) == hash(b)


def test_repr_names_the_type(table):
    assert "Scatter" in repr(qv.Scatter(table, x="x", y="y"))
