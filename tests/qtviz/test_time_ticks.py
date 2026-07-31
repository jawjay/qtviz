"""Roadmap wave 2, increment 2 — calendar-aligned time ticks ([D104]).

`core/_time.time_ticks` picks a calendar unit (seconds → minutes → hours →
days → months → 1/2/5-ladder years) for the visible span and generates
boundary-aligned positions in epoch seconds; matplotlib consumes it through
a Locator (pyqtgraph's `DateAxisItem` is already calendar-native) with the
formatter using the *same* strftime spec, so positions and labels agree.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_EPOCH_2026 = 1_767_225_600.0  # 2026-01-01T00:00Z


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_time_ticks_month_boundaries():
    from qtviz.core._time import time_ticks

    pos, spec = time_ticks(_EPOCH_2026, _EPOCH_2026 + 365 * 86400.0)
    assert spec == "%Y-%m"
    months = pos.astype("datetime64[s]").astype("datetime64[M]")
    back = months.astype("datetime64[s]").astype("int64").astype("float64")
    assert np.array_equal(pos, back)                   # every tick is a month start
    assert 4 <= len(pos) <= 13


@pytest.mark.tier1
def test_time_ticks_day_and_hour_boundaries():
    from qtviz.core._time import time_ticks

    pos, spec = time_ticks(_EPOCH_2026, _EPOCH_2026 + 4 * 86400.0)
    assert spec == "%m-%d"
    assert np.all(pos % 86400.0 == 0)                  # midnight UTC
    pos_h, spec_h = time_ticks(_EPOCH_2026 + 100.0, _EPOCH_2026 + 8 * 3600.0)
    assert spec_h == "%H:%M"
    assert np.all(pos_h % 3600.0 == 0)


@pytest.mark.tier1
def test_time_ticks_year_ladder():
    from qtviz.core._time import time_ticks

    pos, spec = time_ticks(_EPOCH_2026, _EPOCH_2026 + 30 * 365.25 * 86400.0)
    assert spec == "%Y"
    years = pos.astype("datetime64[s]").astype("datetime64[Y]").astype("int64") + 1970
    assert np.all(years % 5 == 0)                      # the 1/2/5 ladder chose 5
    assert len(pos) <= 7


@pytest.mark.tier1
def test_time_ticks_degenerate():
    from qtviz.core._time import time_ticks

    pos, _ = time_ticks(_EPOCH_2026, _EPOCH_2026)
    assert len(pos) == 0


@pytest.mark.tier2
def test_mpl_time_axis_calendar_aligned(qtbot):
    pytest.importorskip("matplotlib")
    days = np.arange("2026-01-01", "2026-07-01",
                     dtype="datetime64[D]").astype("datetime64[ns]")
    el = qv.Curve({"d": days, "v": np.arange(len(days), dtype=float)}, x="d", y="v")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    handle._fig.canvas.draw()
    ax = handle.axes[0]
    locs = np.asarray(ax.get_xticks(), dtype="float64")
    months = locs.astype("datetime64[s]").astype("datetime64[M]")
    back = months.astype("datetime64[s]").astype("int64").astype("float64")
    assert np.array_equal(locs, back)                  # ticks sit on month starts
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert labels[0].startswith("2026-")               # the matching %Y-%m labels


@pytest.mark.tier2
def test_mpl_explicit_ticks_override_time_locator(qtbot):
    pytest.importorskip("matplotlib")
    days = np.arange("2026-01-01", "2026-01-11",
                     dtype="datetime64[D]").astype("datetime64[ns]")
    node = qv.Overlay(
        [qv.Curve({"d": days, "v": np.arange(10.0)}, x="d", y="v")],
        options=qv.OverlayOptions(
            x=qv.AxisSpec(ticks=[_EPOCH_2026 + 3 * 86400], tick_labels=["day 3"])),
    )
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert list(ax.get_xticks()) == [_EPOCH_2026 + 3 * 86400]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["day 3"]
