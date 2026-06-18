"""0.3 axes increment 1 — AxisSpec + declarative limits / invert / aspect, and the
capability-gated scale warn-fallback (no log / no coordinate hazard yet; [D59],
milestone-0.3-firstclass §1). Log rendering + R1 normalization land in increment 2.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core.compose import resolve_scale, surface_of  # noqa: E402
from qtviz.errors import QtvizWarning, ValidationError  # noqa: E402

_DATA = {"x": np.linspace(0.0, 10.0, 50), "y": np.linspace(0.0, 5.0, 50)}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


def _surface(node, **opts):
    return qv.Overlay([node], options=qv.OverlayOptions(**opts))


# ── Tier-1: model + helper (pure) ────────────────────────────────────────────
@pytest.mark.tier1
def test_axisspec_validates_and_is_immutable():
    spec = qv.AxisSpec(label="t", scale="log", lim=(1.0, 100.0), invert=True)
    assert (spec.scale, spec.lim, spec.invert) == ("log", (1.0, 100.0), True)
    with pytest.raises(ValidationError):
        qv.AxisSpec(scale="bogus")
    with pytest.raises(ValidationError):
        qv.AxisSpec(lim=(1.0,))
    with pytest.raises(AttributeError):
        spec.scale = "linear"  # frozen


@pytest.mark.tier1
def test_overlayoptions_axis_config_and_label_convenience():
    # x_label convenience populates x.label; x= carries the full AxisSpec
    o1 = qv.OverlayOptions(x_label="t", y_label="v")
    assert o1.x.label == "t" and o1.y.label == "v"
    assert o1.x_label == "t"  # back-compat read property
    o2 = qv.OverlayOptions(x=qv.AxisSpec(scale="log", lim=(1.0, 10.0)), aspect=1.0)
    assert o2.x.scale == "log" and o2.aspect == 1.0
    # carried by the surface normalizer
    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(invert=True))
    assert surface_of(node).x.invert is True


@pytest.mark.tier1
def test_resolve_scale_warns_and_falls_back():
    assert resolve_scale("log", frozenset({"linear", "log"}), axis="x", backend="b") == "log"
    assert resolve_scale("linear", frozenset({"linear"}), axis="x", backend="b") == "linear"
    with pytest.warns(QtvizWarning, match="not supported"):
        eff = resolve_scale("log", frozenset({"linear"}), axis="x", backend="pyqtgraph")
    assert eff == "linear"


# ── Tier-2: applied on the native backends ───────────────────────────────────
@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_limits_invert_aspect_applied(backend, qtbot):
    if not _has(backend):
        pytest.skip(f"{backend} not registered")
    node = _surface(
        qv.Scatter(_DATA, x="x", y="y"),
        x=qv.AxisSpec(lim=(2.0, 8.0), invert=True), aspect=1.0,
    )
    view = qv.View(node, backend=backend)
    qtbot.addWidget(view)
    if backend == "matplotlib":
        ax = view.handle.axes[0]
        lo, hi = sorted(ax.get_xlim())
        assert (round(lo, 3), round(hi, 3)) == (2.0, 8.0)
        assert ax.xaxis_inverted()
        assert ax.get_aspect() == 1.0
    else:
        vb = view.handle.plots[0].getViewBox()
        (x0, x1), _ = vb.viewRange()
        assert (round(min(x0, x1), 3), round(max(x0, x1), 3)) == (2.0, 8.0)
        assert vb.xInverted()
        assert vb.state["aspectLocked"] == 1.0


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_unsupported_scale_warns_and_renders(backend, qtbot):
    """Increment 1 supports only linear, so a log surface warns and renders (linear)
    — no crash. (Increment 2 turns log on and the warning goes away.)"""
    if not _has(backend):
        pytest.skip(f"{backend} not registered")
    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(scale="log"))
    with pytest.warns(QtvizWarning, match="scale='log'"):
        view = qv.View(node, backend=backend)
        qtbot.addWidget(view)
    assert view.handle is not None  # rendered despite the unsupported scale


# ── Tier-1: webengine figure spec (pure, no display) ─────────────────────────
@pytest.mark.tier1
def test_webengine_layout_carries_limits_invert_aspect():
    from qtviz.backends.webengine import _figure

    node = _surface(
        qv.Scatter(_DATA, x="x", y="y"),
        x=qv.AxisSpec(lim=(1.0, 9.0), invert=True), aspect=2.0,
    )
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    assert layout["xaxis"]["range"] == [1.0, 9.0]
    assert layout["xaxis"]["autorange"] == "reversed"
    assert layout["yaxis"]["scaleanchor"] == "x" and layout["yaxis"]["scaleratio"] == 2.0


@pytest.mark.tier1
def test_webengine_unsupported_scale_warns():
    from qtviz.backends.webengine import _figure

    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(scale="log"))
    with pytest.warns(QtvizWarning, match="scale='log'"):
        _figure.build_figure(node, qv.Theme.light())
