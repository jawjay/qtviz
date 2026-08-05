"""Inset axes ([D152]–[D154], design/inset-axes.md).

I1 (tier-1): the node, validation, pipeline recursion, negotiation.
I2–I4 (tier-2): rendering, pane integration, and the static indicator live
in the sections below as those steps land.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.compose import _elements_of  # noqa: E402
from qtviz.data import node_is_lazy, resolve_node  # noqa: E402
from qtviz.errors import ValidationError  # noqa: E402

D = {"x": np.arange(10.0), "y": np.arange(10.0) ** 2}


def _s(**kw):
    return qv.Scatter(D, x="x", y="y", **kw)


def _zoom():
    return qv.Curve(D, x="x", y="y").opts(x=qv.AxisSpec(lim=(2.0, 4.0)),
                                          y=qv.AxisSpec(lim=(4.0, 16.0)))


# ── I1: the node ─────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_inset_validation():
    ok = qv.Inset(_zoom(), rect=(0.5, 0.5, 0.4, 0.4), label="zoom")
    assert ok.rect == (0.5, 0.5, 0.4, 0.4) and ok.label == "zoom"
    with pytest.raises(ValidationError, match="Element or Overlay"):
        qv.Inset(qv.Layout([_s()]), rect=(0, 0, 0.5, 0.5))
    with pytest.raises(ValidationError, match="Element or Overlay"):
        qv.Inset("not a node", rect=(0, 0, 0.5, 0.5))
    with pytest.raises(ValidationError, match="depth 1"):
        qv.Inset(_s() * qv.Inset(_s(), rect=(0, 0, 0.3, 0.3)),
                 rect=(0, 0, 0.5, 0.5))
    with pytest.raises(ValidationError, match="width/height"):
        qv.Inset(_s(), rect=(0.1, 0.1, 0.0, 0.5))
    with pytest.raises(ValidationError, match="sane"):
        qv.Inset(_s(), rect=(3.0, 0.1, 0.5, 0.5))
    with pytest.raises(ValidationError, match="non-empty"):
        qv.Inset(_s(), rect=(0, 0, 0.5, 0.5), label="")


@pytest.mark.tier1
def test_inset_value_identity():
    child = _s()
    a = qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="z")
    assert a == qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="z")
    assert a != qv.Inset(child, rect=(0.1, 0.5, 0.4, 0.4), label="z")
    assert a != qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="w")
    assert a != qv.Inset(child, rect=(0.5, 0.5, 0.4, 0.4), label="z",
                         indicate=True)


@pytest.mark.tier1
def test_resolve_recurses_into_child():
    inset = qv.Inset(_s(), rect=(0.5, 0.5, 0.4, 0.4))
    node = _s() * inset
    resolved = resolve_node(node)
    inner = [el for el in _elements_of(resolved) if isinstance(el, qv.Scatter)]
    assert len(inner) == 2
    for el in inner:  # both the parent scatter AND the inset's resolved
        assert el.data.resolve_channels(el.channels())["x"].shape == (10,)


@pytest.mark.tier1
def test_lazy_child_marks_node_lazy():
    dd = pytest.importorskip("dask.dataframe")
    pd = pytest.importorskip("pandas")
    df = dd.from_pandas(pd.DataFrame({"x": np.arange(10.0),
                                      "y": np.arange(10.0)}), npartitions=1)
    lazy = qv.Scatter(df, x="x", y="y")
    assert node_is_lazy(lazy)  # premise: a dask-backed ref is lazy
    assert node_is_lazy(_s() * qv.Inset(lazy, rect=(0, 0, 0.4, 0.4)))
    assert not node_is_lazy(_s() * qv.Inset(_s(), rect=(0, 0, 0.4, 0.4)))


@pytest.mark.tier1
def test_negotiation_sees_inset_contents():
    # a RawFigure only renders on webengine; hiding one inside an inset must
    # still steer/inhibit negotiation ([D4] intersect-first via _elements_of)
    raw = qv.RawFigure({"data": [], "layout": {}}, kind="plotly")
    node = _s() * qv.Inset(raw, rect=(0, 0, 0.4, 0.4))
    assert raw in list(_elements_of(node))
    with pytest.raises(qv.errors.QtvizError):
        qv.core.compose.negotiate(node, "pyqtgraph")  # pg can't draw RawFigure


@pytest.mark.tier1
def test_inset_is_chrome_in_series_indexing():
    from qtviz.core.compose import series_index_map

    s1, s2 = _s(), _s()
    children = (s1, qv.Inset(_s(), rect=(0, 0, 0.4, 0.4)), s2)
    assert series_index_map(children) == [0, 0, 1]  # inset shifts nothing
    assert children[1].legend_entry(qv.Theme.light()) is None
