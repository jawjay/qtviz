"""Wave-5 surface ergonomics ([D133]/[D134]).

`.opts()` is pure sugar over `Overlay([el], options=…)` — same nodes, same
value identity; field-wise merge with UNSET semantics; `qv.show(block=False)`
returns a live View; `View.on(source=…)` filters by emitting element.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": np.arange(5.0), "y": np.arange(5.0) ** 2}


@pytest.mark.tier1
def test_element_opts_is_the_overlay_construction():
    el = qv.Curve(_T, x="x", y="y")
    sugared = el.opts(title="Voltage", x="t [s]", y=qv.AxisSpec(scale="log"))
    explicit = qv.Overlay((el,), options=qv.OverlayOptions(
        title="Voltage", x="t [s]", y=qv.AxisSpec(scale="log")))
    assert isinstance(sugared, qv.Overlay)
    assert sugared == explicit  # value identity — the same node, as sugar


@pytest.mark.tier1
def test_opts_merges_field_wise_and_chains():
    node = (qv.Curve(_T, x="x", y="y") * qv.HLine(1.0)).opts(title="T", x="t")
    node = node.opts(y="v")                     # later call, other fields kept
    assert node.options.title == "T"
    assert node.options.x.label == "t" and node.options.y.label == "v"
    spec = node.opts(x=qv.AxisSpec(scale="log"))  # full spec replaces
    assert spec.options.x.scale == "log" and spec.options.x.label is None
    relabel = node.opts(x="t2")                  # bare string merges into label
    assert relabel.options.x.label == "t2"


@pytest.mark.tier1
def test_layout_opts_touches_the_suptitle_and_links():
    lay = (qv.Curve(_T, x="x", y="y") + qv.Histogram(_T, value="y")).opts(
        title="Dash", link_x=True)
    assert lay.options.title == "Dash" and lay.options.link_x
    assert lay.opts(cols=2).options.link_x  # merge keeps earlier fields


@pytest.mark.tier1
def test_reprs_show_non_default_options():
    node = qv.Curve(_T, x="x", y="y").opts(title="Prices")
    assert "title='Prices'" in repr(node)


@pytest.mark.tier2
def test_show_block_false_returns_a_live_view(qtbot):
    view = qv.show(qv.Scatter(_T, x="x", y="y"), title="hello",
                   size=(300, 200), block=False)
    qtbot.addWidget(view)
    assert isinstance(view, qv.View)
    assert view.windowTitle() == "hello"
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    assert qv.show(view, block=False) is view  # an existing View passes through


@pytest.mark.tier2
def test_on_source_filters_by_element(qtbot):
    from qtviz.core.event import PickEvent

    a = qv.Scatter(_T, x="x", y="y")
    b = qv.Scatter(_T, x="x", y="y")
    view = qv.View(a * b)
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=8000)
    got: list = []
    view.on(PickEvent, got.append, source=a, throttle_ms=0)
    view.handle.event_bus.emit(PickEvent(b.id, 0, 1.0, 1.0))
    view.handle.event_bus.emit(PickEvent(a.id, 1, 2.0, 4.0))
    view.handle.event_bus._drain()
    assert [e.source_id for e in got] == [a.id]
