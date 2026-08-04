"""Parity program increment 3 — composition vocabulary ([D84b]/[D90]/[D91]).

`Area` (zero-baseline fill; per-group overlay/stacked bands), `Ecdf`
(core-computed, post-step-drawn), and `Pie` (matplotlib + webengine;
pyqtgraph honestly unsupported — negotiation routes around it).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": [0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
      "y": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
      "g": ["a", "a", "a", "b", "b", "b"]}
_PIE = {"v": [3.0, 2.0, 1.0], "l": ["x", "y", "z"]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1: construction, stats, negotiation ─────────────────────────────────
@pytest.mark.tier1
def test_area_validation():
    from qtviz.errors import ValidationError

    qv.Area(_T, x="x", y="y")
    qv.Area(_T, x="x", y="y", group="g", mode="stacked")
    with pytest.raises(ValidationError):
        qv.Area(_T, x="x", y="y", mode="stacked")  # stacking needs groups
    with pytest.raises(ValidationError):
        qv.Area(_T, x="x", y="y", mode="heap")


@pytest.mark.tier1
def test_pie_validation():
    from qtviz.errors import ValidationError

    qv.Pie(_PIE, value="v", hole=0.5)
    with pytest.raises(ValidationError):
        qv.Pie(_PIE, value="v", hole=1.0)


@pytest.mark.tier1
def test_core_ecdf():
    from qtviz.core._stats import ecdf

    xs, fr = ecdf([3.0, 1.0, 2.0, np.nan])
    assert list(xs) == [1.0, 2.0, 3.0]
    assert np.allclose(fr, [1 / 3, 2 / 3, 1.0])


@pytest.mark.tier1
def test_pie_negotiates_around_pyqtgraph():
    from qtviz.errors import UnsupportedElementError

    el = qv.Pie(_PIE, value="v")
    assert qv.auto_negotiate(el) in ("matplotlib", "webengine")
    if "pyqtgraph" in qv.backends.list_available():
        with pytest.raises(UnsupportedElementError):
            qv.negotiate(el, "pyqtgraph")


# ── tier 1: webengine figure spec (pure) ─────────────────────────────────────
@pytest.mark.tier1
def test_webengine_area_single_fills_to_zero():
    from qtviz.backends.webengine import _figure

    trace = _figure.build_figure(qv.Area(_T, x="x", y="y"),
                                 qv.Theme.light())["data"][0]
    assert trace["fill"] == "tozeroy"


@pytest.mark.tier1
def test_webengine_area_stacked_uses_stackgroup():
    from qtviz.backends.webengine import _figure

    traces = _figure.build_figure(
        qv.Area(_T, x="x", y="y", group="g", mode="stacked"),
        qv.Theme.light())["data"]
    assert len(traces) == 2
    assert all(tr.get("stackgroup") for tr in traces)
    assert [tr["name"] for tr in traces] == ["a", "b"]


@pytest.mark.tier1
def test_webengine_ecdf_is_post_step():
    from qtviz.backends.webengine import _figure

    trace = _figure.build_figure(qv.Ecdf(_T, value="y"),
                                 qv.Theme.light())["data"][0]
    assert trace["line"]["shape"] == "hv"
    assert float(np.max(trace["y"])) == 1.0


@pytest.mark.tier1
def test_webengine_pie_trace():
    from qtviz.backends.webengine import _figure

    trace = _figure.build_figure(qv.Pie(_PIE, value="v", by="l", hole=0.3),
                                 qv.Theme.light())["data"][0]
    assert trace["type"] == "pie" and trace["hole"] == 0.3
    assert trace["labels"] == ["x", "y", "z"]


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_area_single_and_stacked(qtbot):
    pytest.importorskip("matplotlib")
    b = _backend("matplotlib")
    h1 = b.render(qv.Area(_T, x="x", y="y"), theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    assert len(h1.axes[0].collections) == 1  # one PolyCollection
    h2 = b.render(qv.Area(_T, x="x", y="y", group="g", mode="stacked"),
                  theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    assert len(h2.axes[0].collections) == 2  # one band per group
    assert [t.get_text() for t in h2.axes[0].get_legend().get_texts()] == ["a", "b"]


@pytest.mark.tier2
def test_mpl_ecdf_steps_to_one(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Ecdf(_T, value="y")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    line = handle.native(el.id)
    assert line.get_drawstyle() == "steps-post"
    assert float(np.max(line.get_ydata())) == 1.0


@pytest.mark.tier2
def test_mpl_pie_wedges(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Pie(_PIE, value="v", by="l", hole=0.4)
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    wedges = handle.native(el.id)
    assert len(wedges) == 3
    assert wedges[0].width == pytest.approx(0.6)  # donut ring width = 1 - hole
    assert not handle.axes[0].axison


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_area_single_fill_level(qtbot):
    el = qv.Area(_T, x="x", y="y")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id).opts["fillLevel"] == 0.0


@pytest.mark.tier2
def test_pg_area_stacked_fill_between(qtbot):
    import pyqtgraph as pg

    el = qv.Area(_T, x="x", y="y", group="g", mode="stacked")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    items = handle.native(el.id)
    assert len(items) == 2 and all(isinstance(i, pg.FillBetweenItem) for i in items)


@pytest.mark.tier2
def test_pg_ecdf_step_mode(qtbot):
    el = qv.Ecdf(_T, value="y")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.native(el.id).opts["stepMode"] == "left"
