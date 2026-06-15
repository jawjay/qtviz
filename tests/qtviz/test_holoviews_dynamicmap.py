"""Tier-1 + Tier-2 — HoloViews adapter stage 3b (`milestone-holoviews-adapter.md` §7).

DynamicMap one-way reactivity ([D44] Level 1) and the hvplot entry ([D43] Path A).
Spec-first, written against §7's firm API: `from_holoviews(dm) -> Signal[Node]`,
`from_holoviews_dmap(dm) -> (node_signal, {kdim: Signal})`, `from_hvplot(...)`.

The mechanism reuses what already exists: each resolved DynamicMap frame is
translated by the *static* 3a `from_holoviews`, and a `derived` Signal[Node] driven
by per-kdim Signals feeds the View's existing reactive root.

`importorskip` order matters ([D45]): skip on the absent adapter *before* importing
holoviews (numba/bokeh), so collection never imports it while the feature is unbuilt.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
_adapter = pytest.importorskip("qtviz.adapter.holoviews")
# 3b API; until it lands, getattr is None and the module skips rather than erroring.
from_holoviews_dmap = getattr(_adapter, "from_holoviews_dmap", None)
from_hvplot = getattr(_adapter, "from_hvplot", None)
if from_holoviews_dmap is None:
    pytest.skip("stage 3b (from_holoviews_dmap) not implemented yet", allow_module_level=True)
hv = pytest.importorskip("holoviews")

from_holoviews = _adapter.from_holoviews


# ── DynamicMap builders (public hv API only) ─────────────────────────────────
# hv requires a DynamicMap to yield a *single* element type across its key space,
# so we keep the type fixed (Curve) and encode the kdim value into the data: the
# resolved frame's y-series (read back via the qtviz DataRef) proves which key
# was resolved, without relying on element-type changes.
def _continuous_dmap():
    """Single continuous kdim `freq` over (1, 5); y is constant == freq."""

    def cb(freq):
        return hv.Curve(([0, 1, 2], [freq, freq, freq]), "x", "y")

    return hv.DynamicMap(cb, kdims=["freq"]).redim.range(freq=(1.0, 5.0))


def _discrete_dmap():
    """Single discrete kdim `sel` over {lo, hi}; y encodes the choice."""

    def cb(sel):
        v = 1.0 if sel == "lo" else 2.0
        return hv.Curve(([0, 1, 2], [v, v, v]), "x", "y")

    return hv.DynamicMap(cb, kdims=["sel"]).redim.values(sel=["lo", "hi"])


def _two_kdim_dmap():
    """Two discrete kdims; y == [i, j] so each axis is independently verifiable."""

    def cb(i, j):
        return hv.Curve(([0, 1], [i, j]), "x", "y")

    return hv.DynamicMap(cb, kdims=["i", "j"]).redim.values(i=[0, 1], j=[0, 1])


def _y0(node):
    """First y value of a translated Curve, via the qtviz DataRef."""
    return float(node.data.series("y")[0])


def _stream_only_dmap():
    from holoviews.streams import RangeXY

    def cb(x_range=None, y_range=None):
        return hv.Curve(([0, 1], [0, 1]), "x", "y")

    return hv.DynamicMap(cb, streams=[RangeXY()])


# ════════════════════════════ Tier 1 — translation ════════════════════════════


@pytest.mark.tier1
def test_from_holoviews_dmap_exposes_node_signal_and_kdims():
    b = from_holoviews_dmap(_continuous_dmap())
    assert callable(b.node.get) and callable(b.node.subscribe)  # a Signal[Node]
    assert set(b.kdims) == {"freq"}
    assert callable(b.kdims["freq"].get) and callable(b.kdims["freq"].set)


@pytest.mark.tier1
def test_continuous_kdim_default_is_midpoint_and_drives_resolution():
    b = from_holoviews_dmap(_continuous_dmap())
    assert _y0(b.node.get()) == 3.0                # default = midpoint of (1, 5)
    b.kdims["freq"].set(1.0)
    assert _y0(b.node.get()) == 1.0                # set drives re-resolution


@pytest.mark.tier1
def test_discrete_kdim_default_is_first_value_and_drives_resolution():
    b = from_holoviews_dmap(_discrete_dmap())
    assert _y0(b.node.get()) == 1.0                # default = values[0] = "lo"
    b.kdims["sel"].set("hi")
    assert _y0(b.node.get()) == 2.0


@pytest.mark.tier1
def test_two_kdims_resolve_together():
    b = from_holoviews_dmap(_two_kdim_dmap())
    assert set(b.kdims) == {"i", "j"}
    assert b.node.get().data.series("y").tolist() == [0, 0]   # i=0, j=0 defaults
    b.kdims["i"].set(1)
    assert b.node.get().data.series("y").tolist() == [1, 0]   # i drives index 0
    b.kdims["j"].set(1)
    assert b.node.get().data.series("y").tolist() == [1, 1]   # j drives index 1


@pytest.mark.tier1
def test_from_holoviews_on_kdim_map_returns_signal_and_warns():
    """Bare `from_holoviews(dm)` on a kdim-bearing map returns a Signal[Node]
    (the default-frame, undriven) and warns to steer toward from_holoviews_dmap."""
    with pytest.warns(UserWarning, match="from_holoviews_dmap"):
        node = from_holoviews(_continuous_dmap())
    assert callable(node.get) and callable(node.subscribe)
    assert isinstance(node.get(), qv.Curve)


@pytest.mark.tier1
def test_stream_only_dmap_warns_and_returns_static_node():
    """No kdims → can't be widget-driven at L1. Degrade to warn-and-static:
    resolve the current frame natively and warn that stream interactivity is L2."""
    with pytest.warns(UserWarning, match="stream"):
        node = from_holoviews(_stream_only_dmap())
    assert isinstance(node, qv.Curve)              # a plain static Node, not a Signal
    assert not hasattr(node, "subscribe")


@pytest.mark.tier1
def test_from_hvplot_translates_output():
    """hvplot's output is a HoloViews object the adapter already consumes; the
    wrapper is the thin entry. Optional extra — skips when hvplot is absent."""
    if from_hvplot is None:
        pytest.skip("from_hvplot not implemented")
    pytest.importorskip("hvplot")
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"a": np.arange(10.0), "b": np.arange(10.0) ** 2})
    node = from_hvplot(df, "scatter", x="a", y="b")
    # simple scatter → static Node; resolve a Signal[Node] if hvplot returned a DynamicMap
    resolved = node.get() if hasattr(node, "get") and callable(node.get) else node
    assert isinstance(resolved, qv.Scatter)


# ════════════════════════════ Tier 2 — View re-render ═════════════════════════


@pytest.mark.tier2
def test_view_re_renders_when_kdim_signal_changes(qtbot):
    """End-to-end: View(node_signal) re-renders (debounced) when a kdim Signal is
    set — the existing reactive root path, fed by the DynamicMap binding."""
    pytest.importorskip("PySide6.QtWidgets")
    b = from_holoviews_dmap(_discrete_dmap())
    view = qv.View(b.node)
    qtbot.addWidget(view)
    assert view.handle is not None
    assert _y0(view._root) == 1.0                  # default frame ("lo")

    b.kdims["sel"].set("hi")
    qtbot.waitUntil(lambda: _y0(view._root) == 2.0, timeout=1000)
    assert view.handle is not None and not view.loading
