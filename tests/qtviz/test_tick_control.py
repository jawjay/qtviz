"""Roadmap wave 2, increment 1 — tick control ([D101]/[D102]/[D103]).

Explicit `ticks`/`tick_labels` (data-space, R1), one-field format templates
(`"${:,.0f}"`), `minor=` ticks, and `tick_rotation` — honored everywhere
except rotation on pyqtgraph, which the [D109] machinery reports honestly.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": [0.0, 5.0, 10.0], "y": [0.0, 1.0, 0.5]}


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
def test_axis_spec_validation():
    from qtviz.errors import ValidationError

    qv.AxisSpec(ticks=[0, 5, 10], tick_labels=["lo", "mid", "hi"],
                minor=True, tick_rotation=45.0)
    qv.AxisSpec(tick_format="${:,.0f}")
    qv.AxisSpec(tick_format="{:.0f} ms")
    with pytest.raises(ValidationError):
        qv.AxisSpec(tick_labels=["a"])                 # labels need ticks
    with pytest.raises(ValidationError):
        qv.AxisSpec(ticks=[1, 2], tick_labels=["a"])   # length mismatch
    with pytest.raises(ValidationError):
        qv.AxisSpec(tick_format="{bad}{fields}")


@pytest.mark.tier1
def test_template_format_tick():
    from qtviz.core._ticks import format_tick, plotly_tick_parts

    assert format_tick(1234.5, "${:,.0f}") == "$1,234"
    assert format_tick(12.0, "{:.1f} ms") == "12.0 ms"
    assert format_tick(3.0, "{} units") == "3 units"
    assert plotly_tick_parts("${:,.0f}") == ("$", ",.0f", "")
    assert plotly_tick_parts("{:.1f} ms") == ("", ".1f", " ms")
    assert plotly_tick_parts("eng") == ("", "~s", "")
    assert plotly_tick_parts("%H:%M") is None          # date axis handles it


@pytest.mark.tier1
def test_webengine_tick_control():
    from qtviz.backends.webengine import _figure

    node = _surface(x=qv.AxisSpec(ticks=[0.0, 5.0, 10.0], tick_labels=["a", "b", "c"],
                                  minor=True, tick_rotation=30.0),
                    y=qv.AxisSpec(tick_format="${:,.0f}"))
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    ax = layout["xaxis"]
    assert ax["tickvals"] == [0.0, 5.0, 10.0]
    assert ax["ticktext"] == ["a", "b", "c"]
    assert ax["minor"]["ticks"] == "outside"
    assert ax["tickangle"] == -30.0
    assert layout["yaxis"]["tickprefix"] == "$"
    assert layout["yaxis"]["tickformat"] == ",.0f"


@pytest.mark.tier1
def test_webengine_time_ticks_in_ms():
    from qtviz.backends.webengine import _figure

    days = np.arange("2026-01-01", "2026-01-04",
                     dtype="datetime64[D]").astype("datetime64[ns]")
    epoch0 = 1_767_225_600.0
    node = qv.Overlay(
        [qv.Curve({"d": days, "v": [1.0, 2.0, 3.0]}, x="d", y="v")],
        options=qv.OverlayOptions(x=qv.AxisSpec(ticks=[epoch0, epoch0 + 86400])),
    )
    ax = _figure.build_figure(node, qv.Theme.light())["layout"]["xaxis"]
    assert ax["tickvals"] == [epoch0 * 1000.0, (epoch0 + 86400) * 1000.0]


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_tick_control(qtbot):
    pytest.importorskip("matplotlib")
    node = _surface(
        x=qv.AxisSpec(ticks=[0.0, 5.0, 10.0], tick_labels=["lo", "mid", "hi"],
                      tick_rotation=45.0),
        y=qv.AxisSpec(minor=True, tick_format="${:,.0f}"),
    )
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["lo", "mid", "hi"]
    assert ax.get_xticklabels()[0].get_rotation() == 45.0
    assert len(ax.yaxis.get_minorticklocs()) > 0
    assert ax.yaxis.get_major_formatter()(1234.5, 0) == "$1,234"


@pytest.mark.tier2
def test_mpl_explicit_ticks_keep_formatter(qtbot):
    """ticks without labels pin positions but the tick_format still labels."""
    pytest.importorskip("matplotlib")
    node = _surface(x=qv.AxisSpec(ticks=[0.0, 5.0, 10.0], tick_format=".1f"))
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    ax = handle.axes[0]
    handle._fig.canvas.draw()
    assert [t.get_text() for t in ax.get_xticklabels()] == ["0.0", "5.0", "10.0"]


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_explicit_ticks(qtbot):
    node = _surface(x=qv.AxisSpec(ticks=[0.0, 5.0, 10.0], tick_labels=["lo", "mid", "hi"]))
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    axis = handle.plots[0].getAxis("bottom")
    (pairs,) = axis._tickLevels
    assert pairs == [(0.0, "lo"), (5.0, "mid"), (10.0, "hi")]


@pytest.mark.tier2
def test_pg_ticks_logify_under_log(qtbot):
    """R1: explicit ticks are data space; pg positions them in exponent space."""
    node = qv.Overlay(
        [qv.Curve({"x": [1.0, 100.0], "y": [1.0, 2.0]}, x="x", y="y")],
        options=qv.OverlayOptions(x=qv.AxisSpec(scale="log", ticks=[1.0, 10.0, 100.0])),
    )
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    (pairs,) = handle.plots[0].getAxis("bottom")._tickLevels
    assert [p for p, _l in pairs] == [0.0, 1.0, 2.0]   # log10 positions
    assert [lab for _p, lab in pairs] == ["1", "10", "100"]  # data-space labels


@pytest.mark.tier2
def test_pg_tick_rotation_warns(qtbot):
    """[D109] at work: rotation isn't honored on pg — it says so."""
    from qtviz.core import _degrade
    from qtviz.errors import QtvizWarning

    _degrade.reset()
    node = _surface(x=qv.AxisSpec(tick_rotation=45.0))
    with pytest.warns(QtvizWarning, match="tick_rotation"):
        handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
