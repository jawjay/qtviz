"""Named panes ([D145]/[D148], design/pane-handles.md S2).

Labels enter at creation (mapping children, list-form mosaic, `labels=`),
ride the immutable node (surviving `resolve_node` via `with_`), and become
the pane identity downstream — `layout[label]`, `with_pane`, and the
label-keyed state of `test_pane_state.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.compose import flat_pane_labels, parse_mosaic  # noqa: E402
from qtviz.errors import ValidationError  # noqa: E402

D = {"x": np.arange(10.0), "y": np.arange(10.0)}


def _s():
    return qv.Scatter(D, x="x", y="y")


def _c():
    return qv.Curve(D, x="x", y="y")


# ── parse_mosaic list form ───────────────────────────────────────────────────
@pytest.mark.tier1
def test_mosaic_list_form_multi_char_labels():
    cells = parse_mosaic([["price", "book"], ["volume", "book"]])
    assert cells == {"price": (0, 0, 1, 1), "book": (0, 1, 2, 1),
                     "volume": (1, 0, 1, 1)}


@pytest.mark.tier1
def test_mosaic_list_form_holes_and_errors():
    cells = parse_mosaic([["a", None], [".", "b"]])
    assert cells == {"a": (0, 0, 1, 1), "b": (1, 1, 1, 1)}
    with pytest.raises(ValidationError, match="solid rectangle"):
        parse_mosaic([["a", "b"], ["b", "a"]])
    with pytest.raises(ValidationError, match="equal length"):
        parse_mosaic([["a"], ["b", "c"]])
    assert parse_mosaic("AAB;CCB") == parse_mosaic([["A", "A", "B"],
                                                    ["C", "C", "B"]])


# ── labels on Layout ─────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_mapping_children_become_labels():
    lay = qv.Layout.grid({"price": _s(), "volume": _c()})
    assert lay.labels == ("price", "volume")
    assert len(lay.children) == 2


@pytest.mark.tier1
def test_mosaic_retains_labels_and_accepts_mapping_arg():
    lay = qv.Layout.mosaic("AAB;CCB", A=_s(), B=_c(), C=_c())
    assert lay.labels == ("A", "B", "C")  # first-appearance order (row-major)
    lay2 = qv.Layout.mosaic([["p", "b"], ["v", "b"]],
                            {"p": _s(), "b": _c(), "v": _c()})
    assert lay2.labels == ("p", "b", "v")


@pytest.mark.tier1
def test_label_validation():
    with pytest.raises(ValidationError, match="must match children"):
        qv.Layout([_s(), _c()], labels=("only-one",))
    with pytest.raises(ValidationError, match="unique"):
        qv.Layout([_s(), _c()], labels=("a", "a"))
    with pytest.raises(ValidationError, match="non-empty"):
        qv.Layout([_s(), _c()], labels=("a", ""))
    with pytest.raises(ValidationError, match="not both"):
        qv.Layout({"a": _s()}, labels=("b",))


@pytest.mark.tier1
def test_grid_cells_mapping():
    lay = qv.Layout.grid({"a": _s(), "b": _c(), "side": _c()},
                         cells={"a": (0, 0, 1, 1), "b": (1, 0, 1, 1),
                                "side": (0, 1, 2, 1)})
    assert lay.cells == ((0, 0, 1, 1), (1, 0, 1, 1), (0, 1, 2, 1))
    with pytest.raises(ValidationError, match="overlap"):
        qv.Layout.grid({"a": _s(), "b": _c()},
                       cells={"a": (0, 0, 2, 1), "b": (1, 0, 1, 1)})
    with pytest.raises(ValidationError, match="match children labels"):
        qv.Layout.grid({"a": _s()}, cells={"wrong": (0, 0, 1, 1)})
    with pytest.raises(ValidationError, match="mapping children"):
        qv.Layout.grid([_s()], cells={"a": (0, 0, 1, 1)})
    with pytest.raises(ValidationError, match="spans >= 1"):
        qv.Layout([_s()], cells=[(0, 0, 0, 1)])


# ── lookup + with_pane ───────────────────────────────────────────────────────
@pytest.mark.tier1
def test_getitem_by_label_index_and_nested():
    price, volume = _s(), _c()
    lay = qv.Layout.grid({"price": price, "volume": volume})
    assert lay["price"] is price
    assert lay[1] is volume
    outer = qv.Layout([lay, _c()])  # nested lookup reaches inner labels
    assert outer["volume"] is volume
    with pytest.raises(KeyError):
        lay["missing"]
    with pytest.raises(KeyError):
        lay["0"]  # default index labels are positional — int form only


@pytest.mark.tier1
def test_with_pane_swaps_immutably():
    lay = qv.Layout.grid({"price": _s(), "volume": _c()})
    new = _c()
    swapped = lay.with_pane("price", new)
    assert swapped["price"] is new
    assert lay["price"] is not new  # original untouched
    assert swapped.labels == lay.labels and swapped.kind == lay.kind
    outer = qv.Layout([lay, _c()])
    assert outer.with_pane("volume", new)["volume"] is new  # nested
    with pytest.raises(KeyError):
        lay.with_pane("missing", new)


@pytest.mark.tier1
def test_labeled_layout_seals_and_opts_preserves_labels():
    lay = qv.Layout.grid({"a": _s(), "b": _c()})
    grown = lay + _c()  # sealed: nests instead of appending
    assert grown.children[0] is lay and len(grown.children) == 2
    assert lay.opts(cols=1).labels == ("a", "b")
    assert lay.opts(cols=1)["a"] is lay["a"]


# ── flat pane labels (the downstream identity) ───────────────────────────────
@pytest.mark.tier1
def test_flat_pane_labels():
    assert flat_pane_labels(_s()) == ("0",)
    assert flat_pane_labels(_s() + _c()) == ("0", "1")
    lay = qv.Layout.grid({"a": _s(), "b": _c()})
    assert flat_pane_labels(lay) == ("a", "b")
    # nested: inner given labels keep, unlabeled panes get FLAT indices;
    # a Layout child's own label (none here) names the subtree, not a pane
    outer = qv.Layout([lay, _c()])
    assert flat_pane_labels(outer) == ("a", "b", "2")
    with pytest.raises(ValidationError, match="unique"):
        flat_pane_labels(qv.Layout([qv.Layout([_s()], labels=("2",)), _c(), _c()]))


@pytest.mark.tier1
def test_labels_are_value_hashed():
    s = _s()
    a = qv.Layout([s], labels=("a",))
    assert a == qv.Layout([s], labels=("a",))
    assert a != qv.Layout([s], labels=("b",))  # labels are value identity
    assert a != qv.Layout([s])
