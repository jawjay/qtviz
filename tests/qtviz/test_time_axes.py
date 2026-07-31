"""Parity program increment 7 — calendar time ([D94], reopens [D62]).

The canonical time data-space is **epoch seconds (UTC)** on every backend:
datetime64 columns pass through the data layer and become seconds at the
column seam, a linear axis auto-promotes to `scale="time"` when its data is
datetime, and calendar rendering is per-backend dressing (mpl adaptive
strftime formatter, pg `DateAxisItem`, Plotly date axis in ms). Events and
`ViewState` stay plain floats in one space (R1), so time views round-trip
across backend switches. Previously datetime64 silently coerced to
*nanosecond* floats — garbage axes with no warning.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_DT = np.arange("2026-01-01", "2026-01-11", dtype="datetime64[D]").astype("datetime64[ns]")
_T = {"t": _DT, "y": np.arange(10.0)}
_EPOCH0 = 1_767_225_600.0  # 2026-01-01T00:00Z


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1: core ─────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_epoch_seconds_conversion():
    from qtviz.core._time import as_float_seconds, to_epoch_seconds

    secs = to_epoch_seconds(_DT)
    assert secs[0] == _EPOCH0 and secs[1] - secs[0] == 86400.0
    assert np.array_equal(as_float_seconds(_DT), secs)
    assert as_float_seconds([1.0, 2.0]).dtype == np.float64  # numeric passthrough


@pytest.mark.tier1
def test_strftime_tick_format():
    from qtviz.core._ticks import format_tick

    assert format_tick(_EPOCH0, "%Y-%m-%d") == "2026-01-01"
    assert format_tick(0.25, ".0%") == "25%"  # trailing % is still a format spec
    qv.AxisSpec(tick_format="%H:%M")  # validates


@pytest.mark.tier1
def test_auto_time_spec_granularity():
    from qtviz.core._time import auto_time_spec

    assert auto_time_spec(3 * 365 * 86400) == "%Y"
    assert auto_time_spec(90 * 86400) == "%Y-%m"
    assert auto_time_spec(5 * 86400) == "%m-%d"
    assert auto_time_spec(4 * 3600) == "%H:%M"
    assert auto_time_spec(60) == "%H:%M:%S"


@pytest.mark.tier1
def test_datetime_promotes_linear_axis_to_time():
    from qtviz.core.compose import effective_scales, surface_of
    from qtviz.data import resolve_node

    el = resolve_node(qv.Curve(_T, x="t", y="y"))
    x_scale, y_scale = effective_scales(
        el, surface_of(el), frozenset({"linear", "log", "time"}), "test")
    assert (x_scale, y_scale) == ("time", "linear")


@pytest.mark.tier1
def test_datetime_on_timeless_backend_warns_to_linear():
    from qtviz.core.compose import effective_scales, surface_of
    from qtviz.data import resolve_node
    from qtviz.errors import QtvizWarning

    el = resolve_node(qv.Curve(_T, x="t", y="y"))
    with pytest.warns(QtvizWarning, match="time"):
        x_scale, _ = effective_scales(
            el, surface_of(el), frozenset({"linear", "log"}), "stub")
    assert x_scale == "linear"  # still plots — as epoch seconds


@pytest.mark.tier1
def test_time_axis_exempt_from_raster_gate():
    """`time` doesn't transform data, so a raster surface keeps it (unlike
    log/symlog, which force linear)."""
    from qtviz.core.compose import effective_scales
    from qtviz.data import resolve_node

    img = resolve_node(qv.Image(np.zeros((2, 2)), bounds=(0, 0, 1, 1)))
    surf = qv.OverlayOptions(x=qv.AxisSpec(scale="time"))
    x_scale, _ = effective_scales(img, surf, frozenset({"linear", "time"}), "test")
    assert x_scale == "time"


# ── tier 1: webengine (pure figure spec) ─────────────────────────────────────
@pytest.mark.tier1
def test_webengine_time_axis_is_date_in_ms():
    from qtviz.backends.webengine import _figure

    fig = _figure.build_figure(qv.Curve(_T, x="t", y="y"), qv.Theme.light())
    assert fig["layout"]["xaxis"]["type"] == "date"
    x = np.asarray(fig["data"][0]["x"])
    assert x[0] == _EPOCH0 * 1000.0  # Plotly date axes read epoch ms


@pytest.mark.tier1
def test_webengine_date_range_parses_to_seconds():
    from qtviz.backends.webengine._translate import parse_relayout

    x_rng, _ = parse_relayout({"xaxis.range[0]": "2026-01-01",
                               "xaxis.range[1]": "2026-01-02 12:00:00"})
    assert x_rng == (_EPOCH0, _EPOCH0 + 1.5 * 86400)


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_time_axis_plots_seconds_with_calendar_labels(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Curve(_T, x="t", y="y")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    line = handle.native(el.id)
    assert line.get_xdata()[0] == _EPOCH0  # canonical space: epoch seconds
    handle.axes[0].set_xlim(_EPOCH0, _EPOCH0 + 9 * 86400)  # a drawn 10-day view
    fmt = handle.axes[0].xaxis.get_major_formatter()
    assert fmt(_EPOCH0, 0) == "01-01"  # 10-day span → %m-%d granularity
    handle.axes[0].set_xlim(_EPOCH0, _EPOCH0 + 1800)  # zoom to 30 min
    assert fmt(_EPOCH0, 0) == "00:00"  # granularity follows the tick ladder ([D104])
    handle.axes[0].set_xlim(_EPOCH0, _EPOCH0 + 20)  # zoom to seconds
    assert fmt(_EPOCH0, 0) == "00:00:00"


@pytest.mark.tier2
def test_mpl_time_axis_strftime_override(qtbot):
    pytest.importorskip("matplotlib")
    node = qv.Overlay([qv.Curve(_T, x="t", y="y")],
                      options=qv.OverlayOptions(x=qv.AxisSpec(tick_format="%Y/%m/%d")))
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert handle.axes[0].xaxis.get_major_formatter()(_EPOCH0, 0) == "2026/01/01"


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_time_axis_uses_date_axis_item(qtbot):
    import pyqtgraph as pg

    el = qv.Curve(_T, x="t", y="y")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert isinstance(handle.plots[0].getAxis("bottom"), pg.DateAxisItem)
    x, _y = handle.native(el.id).getData()
    assert x[0] == _EPOCH0


@pytest.mark.tier2
def test_time_state_roundtrips_across_backends(qtbot):
    """R1 payoff: one data space (epoch seconds) means a time viewport captured
    on pyqtgraph restores on matplotlib unchanged."""
    pytest.importorskip("matplotlib")
    from qtviz.core.backend import ViewState

    el = qv.Curve(_T, x="t", y="y")
    pg_handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(pg_handle.widget)
    week = (_EPOCH0, _EPOCH0 + 7 * 86400)
    pg_handle.restore_state(ViewState(x_range=week))
    state = pg_handle.capture_state()
    assert state.x_range == pytest.approx(week)  # epoch seconds, not ns/days
    mpl_handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(mpl_handle.widget)
    mpl_handle.restore_state(state)
    assert mpl_handle.axes[0].get_xlim() == pytest.approx(week)
