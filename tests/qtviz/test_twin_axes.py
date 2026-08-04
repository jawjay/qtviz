"""Parity program increment 5 — twin y axes ([D88]).

`Curve`/`Scatter` gain `axis="y2"`; the surface gains `OverlayOptions(y2=
AxisSpec(...))` to configure the right-hand axis that appears when any child
asks for it. Events stay primary-axes (y2 elements are not brush-selectable);
`ViewState` grows an additive `y2_range` so twin ranges survive rebuilds and
backend switches.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": [0.0, 1.0, 2.0], "temp": [10.0, 12.0, 11.0],
      "pressure": [900.0, 1100.0, 1000.0]}


def _dual(**surface):
    return qv.Overlay(
        [qv.Curve(_T, x="x", y="temp"),
         qv.Curve(_T, x="x", y="pressure", axis="y2")],
        options=qv.OverlayOptions(**surface),
    )


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_axis_field_validates():
    from qtviz.errors import ValidationError

    qv.Curve(_T, x="x", y="temp", axis="y2")
    qv.Scatter(_T, x="x", y="temp", axis="y2")
    with pytest.raises(ValidationError):
        qv.Curve(_T, x="x", y="temp", axis="right")
    with pytest.raises(ValidationError):
        qv.Scatter(_T, x="x", y="temp", axis="y2", raster="datashader")


@pytest.mark.tier1
def test_webengine_dual_axis_figure():
    from qtviz.backends.webengine import _figure

    node = _dual(y2=qv.AxisSpec(label="hPa", tick_format=",d"))
    fig = _figure.build_figure(node, qv.Theme.light())
    assert "yaxis" not in fig["data"][0]              # primary stays default
    assert fig["data"][1]["yaxis"] == "y2"
    y2 = fig["layout"]["yaxis2"]
    assert y2["overlaying"] == "y" and y2["side"] == "right"
    assert y2["title"]["text"] == "hPa" and y2["tickformat"] == ",d"


@pytest.mark.tier1
def test_webengine_no_yaxis2_without_y2_children():
    from qtviz.backends.webengine import _figure

    fig = _figure.build_figure(qv.Curve(_T, x="x", y="temp"), qv.Theme.light())
    assert "yaxis2" not in fig["layout"]


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_dual_axis_renders_and_roundtrips_state(qtbot):
    pytest.importorskip("matplotlib")
    node = _dual(y2=qv.AxisSpec(label="hPa", lim=(800.0, 1200.0)))
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    fig = handle.axes[0].figure
    assert len(fig.axes) == 2                          # primary + twin
    ax2 = fig.axes[1]
    assert ax2.get_ylabel() == "hPa"
    assert ax2.get_ylim() == (800.0, 1200.0)
    assert len(ax2.get_lines()) == 1                   # the y2 curve lives there
    state = handle.capture_state()
    assert state.y2_range == (800.0, 1200.0)
    handle.restore_state(qv.core.backend.ViewState(y2_range=(0.0, 1.0)))
    assert ax2.get_ylim() == (0.0, 1.0)


@pytest.mark.tier2
def test_mpl_y2_excluded_from_brush(qtbot):
    pytest.importorskip("matplotlib")
    import numpy as np

    node = _dual()
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    got = []
    handle.event_bus.subscribe(qv.SelectEvent, got.append)
    handle.select_bounds(0, -1.0, -1e6, 3.0, 1e6)      # bounds covering everything
    handle.event_bus._drain()
    assert len(got) == 1                               # only the primary curve
    assert np.array_equal(got[0].indices, [0, 1, 2])


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_dual_axis_renders_in_twin_viewbox(qtbot):
    node = _dual(y2=qv.AxisSpec(label="hPa"))
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    plot = handle.plots[0]
    vb2 = plot._qtviz_vb2
    assert vb2 is not None
    assert plot.getAxis("right").isVisible()
    y2_curve = [el for el in node.children if el.axis == "y2"][0]
    item = handle.native(y2_curve.id)
    assert item.getViewBox() is vb2


@pytest.mark.tier2
def test_pg_y2_state_roundtrip(qtbot):
    from qtviz.core.backend import ViewState

    handle = _backend("pyqtgraph").render(_dual(), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    handle.restore_state(ViewState(y2_range=(500.0, 1500.0)))
    state = handle.capture_state()
    assert state.y2_range == pytest.approx((500.0, 1500.0))


@pytest.mark.tier2
def test_pg_y2_not_brush_selectable(qtbot):
    handle = _backend("pyqtgraph").render(_dual(), theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    vb = handle.plots[0].getViewBox()
    ids = [entry[0] for entry in getattr(vb, "_selectables", [])]
    y2_id = _dual().children[1].id  # fresh node — ids differ; assert by count
    assert len(ids) == 1 and y2_id not in ids
