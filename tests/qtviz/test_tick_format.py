"""Parity program increment 4 — `AxisSpec.tick_format` wired ([D86]).

The long-reserved seam becomes real: `"auto"` keeps each backend's default;
a Python format-spec string or `"eng"` (SI prefixes) formats ticks on all
three backends. Bad specs fail at construction, not render.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": [0.0, 1000.0, 2000.0], "y": [0.0, 0.5, 1.0]}


def _surface(**axes):
    return qv.Overlay([qv.Curve(_T, x="x", y="y")],
                      options=qv.OverlayOptions(**axes))


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_tick_format_validates_at_construction():
    from qtviz.errors import ValidationError

    qv.AxisSpec(tick_format=".2f")
    qv.AxisSpec(tick_format=",d")
    qv.AxisSpec(tick_format=".0%")
    qv.AxisSpec(tick_format="eng")
    with pytest.raises(ValidationError):
        qv.AxisSpec(tick_format="banana")


@pytest.mark.tier1
def test_format_tick_vocabulary():
    from qtviz.core._ticks import format_tick

    assert format_tick(1234.5678, ".2f") == "1234.57"
    assert format_tick(1234567.0, ",d") == "1,234,567"
    assert format_tick(0.25, ".0%") == "25%"
    assert format_tick(1500.0, "eng") == "1.5k"
    assert format_tick(0.002, "eng") == "2m"
    assert format_tick(0.0, "eng") == "0"


@pytest.mark.tier1
def test_webengine_layout_carries_tickformat():
    from qtviz.backends.webengine import _figure

    node = _surface(x=qv.AxisSpec(tick_format=",d"), y=qv.AxisSpec(tick_format="eng"))
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    assert layout["xaxis"]["tickformat"] == ",d"
    assert layout["yaxis"]["tickformat"] == "~s"  # eng → d3 SI suffix
    assert "tickformat" not in _figure.build_figure(
        _surface(), qv.Theme.light())["layout"]["xaxis"]


# ── tier 2 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_tick_formatter_applied(qtbot):
    pytest.importorskip("matplotlib")
    node = _surface(x=qv.AxisSpec(tick_format="eng"), y=qv.AxisSpec(tick_format=".0%"))
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert ax.xaxis.get_major_formatter()(1500.0, 0) == "1.5k"
    assert ax.yaxis.get_major_formatter()(0.5, 0) == "50%"


@pytest.mark.tier2
def test_pg_tick_strings_applied(qtbot):
    node = _surface(x=qv.AxisSpec(tick_format=",d"))
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    axis = handle.plots[0].getAxis("bottom")
    assert axis.tickStrings([1234567.0], 1.0, 1.0) == ["1,234,567"]


@pytest.mark.tier2
def test_pg_tick_format_under_log_labels_data_space(qtbot):
    """R1: pg's log axis lives in exponent space — the formatted label must
    still read data space (10**v)."""
    data = {"x": [1.0, 10.0, 100.0], "y": [1.0, 10.0, 100.0]}
    node = qv.Overlay(
        [qv.Curve(data, x="x", y="y")],
        options=qv.OverlayOptions(
            y=qv.AxisSpec(scale="log", tick_format=",d")),
    )
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    axis = handle.plots[0].getAxis("left")
    assert axis.tickStrings([2.0], 1.0, 1.0) == ["100"]  # exponent 2 → data 100
