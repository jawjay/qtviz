"""Roadmap wave 1, increment 4 — surface-option honor-or-warn ([D109]).

Element options had the anti-silent-drop guard since 0.2; surface options
kept slipping through (`LayoutOptions.rows`/`spacing`/`title`). Consumers now
declare what they honor: the three backends honor the full OverlayOptions/
AxisSpec surface, backend-hosted grids honor cols/link only, and the Qt
layout host honors cols/spacing/tabs/docks — everything else warns once.
"""

from __future__ import annotations

import warnings

import pytest

qv = pytest.importorskip("qtviz")
from qtviz.core import _degrade  # noqa: E402
from qtviz.errors import QtvizWarning  # noqa: E402

_T = {"x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 0.5]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_surface_overrides_detection():
    from qtviz.core._degrade import surface_overrides

    assert surface_overrides(qv.OverlayOptions()) == []
    got = surface_overrides(qv.OverlayOptions(
        title="T", grid=False, x=qv.AxisSpec(scale="log", lim=(1, 10)),
        y2=qv.AxisSpec(label="p")))
    assert set(got) == {"title", "grid", "x.scale", "x.lim", "y2"}


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_fully_wired_surface_does_not_warn(backend, qtbot):
    """Every OverlayOptions/AxisSpec field is honored on the built-ins — the
    [D109] guard must stay silent for all of them."""
    b = _backend(backend)
    node = qv.Overlay(
        [qv.Curve(_T, x="x", y="y", label="c")],
        options=qv.OverlayOptions(
            title="T", y="y", aspect=1.0, grid=False,
            legend="right", background="#eeeeee",
            x=qv.AxisSpec(label="x", lim=(0.0, 2.0), invert=True, tick_format=".1f"),
        ),
    )
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        handle = b.render(node, theme=qv.Theme.light())
        qtbot.addWidget(handle.widget)
        handle.dispose()
    assert not [w for w in caught if issubclass(w.category, QtvizWarning)]


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_unhonored_layout_options_warn(backend, qtbot):
    """Layout options a backend grid can't render (tab chrome, host spacing)
    must warn instead of silently vanishing (the audit's recurring finding).
    rows/title/ratios graduated to honored in [D108]."""
    b = _backend(backend)
    node = qv.Layout(
        [qv.Curve(_T, x="x", y="y"), qv.Curve(_T, x="x", y="y")],
        options=qv.LayoutOptions(spacing=20, tab_labels=("a", "b")),
    )
    _degrade.reset()
    with pytest.warns(QtvizWarning) as caught:
        handle = b.render(node, theme=qv.Theme.light())
        qtbot.addWidget(handle.widget)
        handle.dispose()
    msgs = " | ".join(str(w.message) for w in caught)
    assert "'spacing'" in msgs and "'tab_labels'" in msgs


@pytest.mark.tier2
def test_host_layout_honesty(qtbot):
    """The Qt host honors spacing/tabs — and, since [D151], link_x/link_y
    across host panes (the `_LinkController`): no honesty warning, and a zoom
    in one pane propagates to the linked one."""
    import warnings as _w

    from qtviz.core._host import LayoutHost

    node = qv.Layout(
        [qv.Curve(_T, x="x", y="y"), qv.Curve(_T, x="x", y="y")],
        kind="tabs",
        options=qv.LayoutOptions(tab_labels=("a", "b"), link_x=True),
    )
    _degrade.reset()
    with _w.catch_warnings():
        _w.simplefilter("error", QtvizWarning)  # honored ⇒ silent
        handle = LayoutHost.render(node, view_backend="pyqtgraph",
                                   theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    handle.pane("0").set_range(x=(2.0, 7.0))
    handle.event_bus._drain()
    assert handle.pane("1").capture().x_range == pytest.approx((2.0, 7.0), rel=1e-3)
    handle.dispose()


@pytest.mark.tier1
def test_warns_once_per_consumer_option():
    from qtviz.core._degrade import check_layout

    _degrade.reset()
    opts = qv.LayoutOptions(rows=3)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_layout(opts, consumer="stub", honored=frozenset())
        check_layout(opts, consumer="stub", honored=frozenset())
    assert len([w for w in caught if issubclass(w.category, QtvizWarning)]) == 1
