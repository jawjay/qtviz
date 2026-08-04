"""0.3 axes — increment 1 (AxisSpec + declarative limits / invert / aspect + the
capability-gated scale warn-fallback) and increment 2 (log rendering + the R1
coordinate normalization; [D59], milestone-0.3-firstclass §1).

The R1 contract under test: every coordinate that crosses the seam —
capture/restore state, RangeEvent, SelectEvent bounds, pick/hover — is in **data
space**, never log/exponent space (feasibility §10.3).
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
    # [D133]: a bare string is the axis label — AxisSpec.label the one home
    o1 = qv.OverlayOptions(x="t", y="v")
    assert o1.x.label == "t" and o1.y.label == "v"
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
def test_unsupported_scale_warns_and_renders(qtbot):
    """A scale outside the backend's `Capabilities.scales` warns and renders linear —
    no crash. `time` graduated from reserved to supported ([D94]), so the probe is
    `symlog`, which stays matplotlib-only (pyqtgraph #1035)."""
    if not _has("pyqtgraph"):
        pytest.skip("pyqtgraph not registered")
    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(scale="symlog"))
    with pytest.warns(QtvizWarning, match="scale='symlog'"):
        view = qv.View(node, backend="pyqtgraph")
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

    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(scale="symlog"))
    with pytest.warns(QtvizWarning, match="scale='symlog'"):
        _figure.build_figure(node, qv.Theme.light())


# ═══════════════════════════════════════════════════════════════════════════════
# Increment 2 — log scale + R1 coordinate normalization
# ═══════════════════════════════════════════════════════════════════════════════

_LOG_DATA = {"x": np.array([1.0, 10.0, 100.0, 1000.0]),
             "y": np.array([1.0, 2.0, 3.0, 4.0])}


# ── Tier-1: the pure helpers ─────────────────────────────────────────────────
@pytest.mark.tier1
def test_logify_masks_nonpositive_and_warns_once():
    import warnings

    from qtviz.core._scales import logify

    a = np.array([-1.0, 0.0, 10.0, 100.0])
    with pytest.warns(QtvizWarning, match="non-positive"):
        out = logify(a, True)
    assert np.isnan(out[0]) and np.isnan(out[1])          # dropped (masked to NaN)
    assert out[2] == 1.0 and out[3] == 2.0                # log10, index-aligned
    assert len(out) == len(a)                             # never shortens (pick fidelity)
    # linear passes through untouched; all-positive log emits no warning
    b = np.array([1.0, 10.0])
    assert logify(b, False) is b
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert np.allclose(logify(b, True), [0.0, 1.0])


@pytest.mark.tier1
def test_delog():
    from qtviz.core._scales import delog

    assert delog(2.0, True) == 100.0
    assert delog(2.0, False) == 2.0


@pytest.mark.tier1
def test_effective_scales_gates_rasters():
    """Image/Heatmap (incl. datashaded rasters, which resolve to Image) under a
    non-linear scale warn and force linear — a raster is never log-transformed."""
    from qtviz.core.compose import effective_scales

    scales = frozenset({"linear", "log"})
    plain = _surface(qv.Scatter(_LOG_DATA, x="x", y="y"), x=qv.AxisSpec(scale="log"))
    assert effective_scales(plain, surface_of(plain), scales, "pyqtgraph") == ("log", "linear")

    raster = _surface(qv.Image(np.zeros((4, 4)), extent=(0.0, 0.0, 1.0, 1.0)),
                      x=qv.AxisSpec(scale="log"))
    with pytest.warns(QtvizWarning, match="raster"):
        eff = effective_scales(raster, surface_of(raster), scales, "pyqtgraph")
    assert eff == ("linear", "linear")


# ── Tier-2: log rendering on the native backends ─────────────────────────────
@pytest.mark.tier2
def test_pyqtgraph_log_axis_and_pretransformed_data(qtbot):
    """Approach A: data pre-log10'd in the renderer + AxisItem in log-tick mode."""
    el = qv.Scatter(_LOG_DATA, x="x", y="y")
    view = qv.View(_surface(el, x=qv.AxisSpec(scale="log")), backend="pyqtgraph")
    qtbot.addWidget(view)
    plot = view.handle.plots[0]
    assert plot.getAxis("bottom").logMode
    assert not plot.getAxis("left").logMode
    vb = plot.getViewBox()
    assert vb.x_log and not vb.y_log
    xs, _ys = view.handle.native(el.id).getData()
    assert np.allclose(xs, [0.0, 1.0, 2.0, 3.0])          # exponent space internally


@pytest.mark.tier2
def test_matplotlib_log_scale_applied(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(_surface(qv.Scatter(_LOG_DATA, x="x", y="y"),
                            x=qv.AxisSpec(scale="log")), backend="matplotlib")
    qtbot.addWidget(view)
    ax = view.handle.axes[0]
    assert ax.get_xscale() == "log"
    # matplotlib limits stay data-space under log — capture_state needs no R1
    lo, hi = view.handle.capture_state().x_range
    assert lo > 0 and hi >= 100.0


@pytest.mark.tier2
def test_symlog_capability_gate(qtbot):
    """symlog renders on matplotlib; pyqtgraph warns → linear (exercises the gate)."""
    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(scale="symlog"))
    if _has("matplotlib"):
        view = qv.View(node, backend="matplotlib")
        qtbot.addWidget(view)
        assert view.handle.axes[0].get_xscale() == "symlog"
    with pytest.warns(QtvizWarning, match="scale='symlog'"):
        view2 = qv.View(node, backend="pyqtgraph")
        qtbot.addWidget(view2)
    assert not view2.handle.plots[0].getViewBox().x_log


# ── Tier-2: R1 — every boundary emits data space (the critical tests) ────────
@pytest.mark.tier2
def test_r1_range_event_is_data_space(qtbot):
    view = qv.View(_surface(qv.Scatter(_LOG_DATA, x="x", y="y"),
                            x=qv.AxisSpec(scale="log")), backend="pyqtgraph")
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.RangeEvent, got.append, throttle_ms=0)
    vb = view.handle.plots[0].getViewBox()
    vb.setXRange(0.0, 2.0, padding=0)                     # exponent space: 10^0..10^2
    assert got, "no RangeEvent emitted"
    (x0, x1) = got[-1].x
    assert np.allclose((x0, x1), (1.0, 100.0))            # …but the event is data space


@pytest.mark.tier2
def test_r1_select_bounds_and_indices_data_space(qtbot):
    el = qv.Scatter(_LOG_DATA, x="x", y="y")
    view = qv.View(_surface(el, x=qv.AxisSpec(scale="log")), backend="pyqtgraph")
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0)
    vb = view.handle.plots[0].getViewBox()
    # programmatic brush takes DATA-space bounds; x in [5, 500] → rows 1, 2
    vb.select_bounds(5.0, 0.0, 500.0, 10.0)
    assert got and got[-1].indices == [1, 2]
    assert got[-1].bounds == (5.0, 0.0, 500.0, 10.0)      # bounds pass through data space
    # the drag gesture maps view coords (exponent space) → data space before masking
    assert np.isclose(vb._to_data_x(1.0), 10.0)
    assert vb._to_data_y(3.0) == 3.0                      # y is linear here


@pytest.mark.tier2
def test_r1_pick_event_is_data_space(qtbot):
    el = qv.Scatter(_LOG_DATA, x="x", y="y")
    view = qv.View(_surface(el, x=qv.AxisSpec(scale="log")), backend="pyqtgraph")
    qtbot.addWidget(view)
    got: list = []
    view.on(qv.PickEvent, got.append, throttle_ms=0)
    item = view.handle.native(el.id)
    pts = item.points()
    item.sigClicked.emit(item, pts[1:2], None)            # point at data x=10 (exponent 1)
    assert got and np.isclose(got[-1].x, 10.0)
    assert got[-1].point_index == 1                       # NaN-masking keeps row alignment


@pytest.mark.tier2
def test_r1_capture_restore_round_trip_under_log(qtbot):
    from qtviz.core.backend import ViewState

    view = qv.View(_surface(qv.Scatter(_LOG_DATA, x="x", y="y"),
                            x=qv.AxisSpec(scale="log")), backend="pyqtgraph")
    qtbot.addWidget(view)
    handle = view.handle
    handle.restore_state(ViewState(x_range=(1.0, 100.0)))  # data space in …
    vb = view.handle.plots[0].getViewBox()
    (x0, x1), _ = vb.viewRange()
    assert np.allclose((x0, x1), (0.0, 2.0))               # exponent space internally
    st = handle.capture_state()
    assert np.allclose(st.x_range, (1.0, 100.0))           # … data space out


@pytest.mark.tier2
def test_r1_survives_backend_switch(qtbot):
    """Backend swap under log keeps data-space ranges (ViewState is portable, [D2])."""
    from qtviz.core.backend import ViewState

    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(_surface(qv.Scatter(_LOG_DATA, x="x", y="y"),
                            x=qv.AxisSpec(scale="log")), backend="pyqtgraph")
    qtbot.addWidget(view)
    view.handle.restore_state(ViewState(x_range=(1.0, 100.0), y_range=(1.0, 4.0)))
    view.set_backend("matplotlib")
    lo, hi = view.handle.capture_state().x_range
    assert np.allclose((lo, hi), (1.0, 100.0))


@pytest.mark.tier2
def test_viewstate_wins_over_declarative_lim_after_rebuild(qtbot):
    """[D59] precedence: `AxisSpec.lim` sets the initial range; a live pan/zoom
    (ViewState) restored after render wins across rebuilds."""
    node = _surface(qv.Scatter(_DATA, x="x", y="y"), x=qv.AxisSpec(lim=(2.0, 8.0)))
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    view.handle.plots[0].getViewBox().setXRange(3.0, 4.0, padding=0)  # user zoom
    view.set_root(node)                                               # rebuild
    (x0, x1), _ = view.handle.plots[0].getViewBox().viewRange()
    assert np.allclose((x0, x1), (3.0, 4.0))              # zoom wins, not lim


@pytest.mark.tier2
def test_nonpositive_data_under_log_warns_and_renders(qtbot):
    data = {"x": np.array([-5.0, 0.0, 1.0, 10.0]), "y": np.array([1.0, 2.0, 3.0, 4.0])}
    node = _surface(qv.Scatter(data, x="x", y="y"), x=qv.AxisSpec(scale="log"))
    with pytest.warns(QtvizWarning, match="non-positive"):
        view = qv.View(node, backend="pyqtgraph")
        qtbot.addWidget(view)
    assert view.handle is not None


@pytest.mark.tier2
def test_datashader_under_log_warns_and_renders_linear(qtbot):
    pytest.importorskip("datashader")
    rng = np.random.default_rng(7)
    data = {"x": rng.uniform(1.0, 100.0, 5000), "y": rng.normal(size=5000)}
    node = _surface(qv.Scatter(data, x="x", y="y", raster="datashader"),
                    x=qv.AxisSpec(scale="log"))
    with pytest.warns(QtvizWarning, match="raster"):
        view = qv.View(node, backend="pyqtgraph")
        qtbot.addWidget(view)
        # datashaded roots resolve async — the render (where the gate fires)
        # happens once the loop spins
        qtbot.waitUntil(lambda: view.handle is not None, timeout=5000)
    assert not view.handle.plots[0].getViewBox().x_log    # gated to linear, no crash


# ── Tier-1: webengine log figure spec (pure, no display) ─────────────────────
@pytest.mark.tier1
def test_webengine_log_axis_type_and_log10_range():
    from qtviz.backends.webengine import _figure

    node = _surface(qv.Scatter(_LOG_DATA, x="x", y="y"),
                    x=qv.AxisSpec(scale="log", lim=(1.0, 100.0)))
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    assert layout["xaxis"]["type"] == "log"
    assert np.allclose(layout["xaxis"]["range"], [0.0, 2.0])  # Plotly log range is log10
    assert "type" not in layout["yaxis"]                       # linear stays untyped
