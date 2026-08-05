"""Dynamic datashading on the webengine backend (4b closes the gap).

The Plotly RasterTarget rides the `plotly.view` bridge message (ranges +
plot-area px from JS) and writes re-aggregated rasters back as a restyle of the
image trace's PNG `source`. Orientation contract (probed against the bundled
plotly.js): z row 0 lands at `y0` (= qtviz's row-0-is-ymin on a y-up axis);
`source` PNGs blit naturally (first row = ymax), so encoding flips; an image
trace reverses the y axis unless the layout pins `autorange: true`.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
pytest.importorskip("plotly")

from qtviz.core.event import HoverEvent  # noqa: E402

pytestmark = pytest.mark.tier2


# ── pure helpers: PNG encoding + placement (no Chromium) ─────────────────────
def test_png_encode_flips_to_natural_image_order():
    from qtviz.backends.webengine._raster import encode_raster_png

    RED, BLUE = [255, 0, 0, 255], [0, 0, 255, 255]
    rgba = np.array([[RED, RED], [BLUE, BLUE]], dtype=np.uint8)  # row 0 = ymin = red
    uri = encode_raster_png(rgba)
    assert uri.startswith("data:image/png;base64,")

    import base64

    from PySide6.QtGui import QImage

    img = QImage.fromData(base64.b64decode(uri.split(",", 1)[1]))
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    assert img.pixelColor(0, 0).getRgb()[:3] == (0, 0, 255)  # PNG top row = ymax = blue
    assert img.pixelColor(0, 1).getRgb()[:3] == (255, 0, 0)  # PNG bottom row = ymin = red


def test_raster_placement_maps_edge_bounds_to_pixel_centers():
    from qtviz.backends.webengine._raster import raster_placement

    p = raster_placement((2, 4), (0.0, 0.0, 8.0, 2.0))  # 2 rows × 4 cols
    assert p == {"x0": 1.0, "dx": 2.0, "y0": 0.5, "dy": 1.0}


def test_runtime_reports_the_view():
    from qtviz.backends.webengine.ext.plotly._runtime import PLOTLY_JS

    assert "plotly.view" in PLOTLY_JS  # the raster loop's viewport feed


# ── figure build: source-mode raster trace, extent, y-up pin ─────────────────
def _datashaded_scatter(n=2000, seed=7):
    rng = np.random.default_rng(seed)
    return qv.Scatter({"x": rng.normal(size=n), "y": rng.normal(size=n)},
                      x="x", y="y", raster="datashader")


def test_datashaded_trace_is_source_mode_and_placed():
    pytest.importorskip("datashader")
    from qtviz.backends.webengine import _figure

    fig, source_ids = _figure.build(_datashaded_scatter(), qv.Theme.light())
    (trace,) = fig["data"]
    assert trace["type"] == "image"
    assert trace["source"].startswith("data:image/png;base64,")
    assert "z" not in trace
    assert trace["dx"] > 0 and trace["dy"] > 0
    assert trace["hoverinfo"] == "x+y"
    assert fig["layout"]["yaxis"]["autorange"] is True  # y-up despite the image trace
    assert len(source_ids) == 1  # one trace, carrying the source element's id


def test_user_rgba_image_trace_carries_extent():
    from qtviz.backends.webengine import _figure

    rgba = np.zeros((4, 3, 4), dtype=np.uint8)
    fig, _ = _figure.build(qv.Image(rgba, extent=(0.0, 0.0, 3.0, 4.0)), qv.Theme.light())
    (trace,) = fig["data"]
    assert trace["type"] == "image"
    assert (trace["x0"], trace["dx"]) == (0.5, 1.0)
    assert (trace["y0"], trace["dy"]) == (0.5, 1.0)
    assert fig["layout"]["yaxis"]["autorange"] is True


def test_inverted_axis_keeps_its_reversal():
    from qtviz.backends.webengine import _figure

    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    node = qv.Image(rgba, extent=(0.0, 0.0, 2.0, 2.0)).opts(y=qv.AxisSpec(invert=True))
    fig, _ = _figure.build(node, qv.Theme.light())
    assert fig["layout"]["yaxis"]["autorange"] == "reversed"  # the pin must not override


# ── the RasterTarget over the bridge (offscreen WebBridgeView, no page) ──────
@pytest.fixture
def bridge_target(qtbot):
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    from qtviz.backends.webengine._raster import PlotlyRasterTarget
    from qtviz.backends.webengine.core.web_bridge_view import WebBridgeView
    from qtviz.backends.webengine.ext.plotly.backend import PlotlyBackend

    view = WebBridgeView()
    qtbot.addWidget(view)
    host = PlotlyBackend({"data": [], "layout": {}})
    host._view = view  # attach transport only — no page load offscreen
    target = PlotlyRasterTarget(host, view, 2, home=(0.0, 0.0, 10.0, 10.0))
    return view, host, target


def _queued(view, name):
    return [payload for n, payload in view._command_queue if n == name]


def test_target_reads_viewport_from_view_messages(bridge_target):
    view, _host, target = bridge_target
    fired = []
    sub = target.connect_viewport(lambda: fired.append(1))
    assert target.viewport() is None  # nothing seen yet — controller waits

    view._emit_received("plotly.view", {"x": [0.0, 10.0], "y": [0.0, 5.0], "w": 300, "h": 200})
    assert target.viewport() == ((0.0, 10.0), (0.0, 5.0))
    assert target.pixel_size() == (300, 200)
    assert len(fired) == 1

    # an identical echo (our own pin/restyle round-trip) must not re-fire
    view._emit_received("plotly.view", {"x": [0.0, 10.0], "y": [0.0, 5.0], "w": 300, "h": 200})
    assert len(fired) == 1

    view._emit_received("plotly.view", {"x": [1.0, 2.0], "y": [0.0, 5.0], "w": 300, "h": 200})
    assert len(fired) == 2
    sub.dispose()
    view._emit_received("plotly.view", {"x": [3.0, 4.0], "y": [0.0, 5.0], "w": 300, "h": 200})
    assert len(fired) == 2  # unsubscribed


def test_set_raster_pins_axes_then_restyles_the_trace(bridge_target):
    view, _host, target = bridge_target
    target.connect_viewport(lambda: None)
    view._emit_received("plotly.view", {"x": [0.0, 10.0], "y": [0.0, 5.0], "w": 300, "h": 200})

    target.set_raster(np.zeros((4, 4, 4), dtype=np.uint8), (0.0, 0.0, 10.0, 5.0))

    (pin,) = _queued(view, "plotly.relayout")
    assert pin["update"]["xaxis.range"] == [0.0, 10.0]
    assert pin["update"]["xaxis.autorange"] is False  # P2 drift family: raster must not steer
    (restyle,) = _queued(view, "plotly.restyle")
    assert restyle["indices"] == [2]
    update = restyle["update"]
    assert update["source"][0].startswith("data:image/png;base64,")
    assert update["x0"] == [1.25] and update["dx"] == [2.5]
    assert update["y0"] == [0.625] and update["dy"] == [1.25]

    # second write: axes already pinned — no second relayout
    target.set_raster(np.zeros((4, 4, 4), dtype=np.uint8), (0.0, 0.0, 10.0, 5.0))
    assert len(_queued(view, "plotly.relayout")) == 1
    assert len(_queued(view, "plotly.restyle")) == 2


def test_double_click_autorange_restores_the_home_extent(bridge_target):
    view, _host, target = bridge_target
    target.connect_viewport(lambda: None)
    view._emit_received("plotly.view", {"x": [2.0, 3.0], "y": [2.0, 3.0], "w": 300, "h": 200})
    target.set_raster(np.zeros((2, 2, 4), dtype=np.uint8), (2.0, 2.0, 3.0, 3.0))  # pins

    view._emit_received("plotly.relayout", {"update": {"xaxis.autorange": True,
                                                       "yaxis.autorange": True}})
    home = _queued(view, "plotly.relayout")[-1]
    assert home["update"]["xaxis.range"] == [0.0, 10.0]  # the full-data extent
    assert home["update"]["yaxis.range"] == [0.0, 10.0]


# ── wiring: render() attaches controllers; hover carries the value ───────────
def test_render_wires_controllers_and_hover_values(qtbot):
    pytest.importorskip("datashader")
    pytest.importorskip("PySide6.QtWebEngineWidgets")
    if "webengine" not in qv.backends.list_available():
        pytest.skip("webengine backend not registered")
    from qtviz.ext.datashader import RasterAggregate

    el = _datashaded_scatter()
    handle = qv.backends.get("webengine").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    try:
        (controller,) = handle._rasters
        assert controller.element_id == el.id
        holder = handle._raster_holders[el.id]
        assert holder.aggregate is not None  # [D46] hover view, live from the start

        # a hover translated over the raster trace picks up the aggregated value
        holder.aggregate = RasterAggregate(np.array([[7.0]]), (0.0, 0.0, 1.0, 1.0), "mean")
        seen: list = []
        handle.event_bus.subscribe(HoverEvent, seen.append, throttle_ms=0)
        handle._on_message("plotly.hover", {"points": [
            {"trace_index": 0, "point_index": None, "x": 0.5, "y": 0.5}]})
        assert len(seen) == 1 and seen[0].value == 7.0
    finally:
        handle.dispose()
    assert handle._rasters == [] and handle._raster_holders == {}
