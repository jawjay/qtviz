"""W1 webengine — the pure Element→Plotly and event-translation core.

No Qt, no WebEngine: these run headless and prove the figure builder and the
D27 event map independent of the live render path (which is display-gated, in
`test_webengine_render.py`).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.backends.webengine import _figure, _translate  # noqa: E402

pytestmark = pytest.mark.tier1


# ── figure builder ───────────────────────────────────────────────────────────
def test_scatter_builds_one_scattergl_trace(table):
    fig = _figure.build_figure(qv.Scatter(table, x="x", y="y"), qv.Theme.light())

    assert isinstance(fig, dict) and "data" in fig and "layout" in fig
    assert len(fig["data"]) == 1
    trace = fig["data"][0]
    assert trace["type"] == "scattergl"
    assert trace["mode"] == "markers"
    assert np.allclose(trace["x"], table["x"])
    assert np.allclose(trace["y"], table["y"])
    # static color → a single css color string
    assert isinstance(trace["marker"]["color"], str)
    assert trace["marker"]["color"].startswith("rgb(")


def test_overlay_builds_one_trace_per_element(table):
    overlay = qv.Scatter(table, x="x", y="y") * qv.Scatter(table, x="x", y="z")
    fig = _figure.build_figure(overlay, qv.Theme.light())
    assert len(fig["data"]) == 2


def test_color_by_maps_per_point_colors(table):
    fig = _figure.build_figure(qv.Scatter(table, x="x", y="y", color_by="z"), qv.Theme.light())
    color = fig["data"][0]["marker"]["color"]
    assert isinstance(color, list)
    assert len(color) == len(table["x"])
    assert all(c.startswith("rgb(") for c in color)


def test_size_by_scales_per_point_sizes(table):
    fig = _figure.build_figure(qv.Scatter(table, x="x", y="y", size_by="z"), qv.Theme.light())
    size = fig["data"][0]["marker"]["size"]
    assert isinstance(size, list)
    assert len(size) == len(table["x"])
    assert min(size) >= 5.0 - 1e-9


def test_layout_carries_theme(table):
    dark = _figure.build_figure(qv.Scatter(table, x="x", y="y"), qv.Theme.dark())["layout"]
    light = _figure.build_figure(qv.Scatter(table, x="x", y="y"), qv.Theme.light())["layout"]
    assert dark["paper_bgcolor"] != light["paper_bgcolor"]
    assert dark["xaxis"]["gridcolor"].startswith("rgb(")


def test_supports_all_eight_elements():
    names = {t.__name__ for t in _figure.supported_types()}
    assert names == {
        "Scatter", "Curve", "Bars", "Histogram", "Image", "Heatmap", "ErrorBars", "Spread",
    }


def test_every_element_builds_at_least_one_trace(make_elements):
    for name, el in make_elements(qv).items():
        fig = _figure.build_figure(el, qv.Theme.light())
        assert fig["data"], f"{name} produced no traces"
        assert all("type" in tr for tr in fig["data"])


def test_element_trace_shapes(make_elements):
    els = make_elements(qv)
    light = qv.Theme.light()
    assert _figure.build_figure(els["Curve"], light)["data"][0]["mode"] == "lines"
    assert _figure.build_figure(els["Bars"], light)["data"][0]["type"] == "bar"
    assert _figure.build_figure(els["Histogram"], light)["data"][0]["type"] == "histogram"
    assert _figure.build_figure(els["Image"], light)["data"][0]["type"] == "heatmap"
    assert _figure.build_figure(els["Heatmap"], light)["data"][0]["type"] == "heatmap"
    assert "error_y" in _figure.build_figure(els["ErrorBars"], light)["data"][0]
    spread = _figure.build_figure(els["Spread"], light)["data"]
    assert len(spread) == 2 and spread[1]["fill"] == "tonexty"


def test_unsupported_element_raises():
    from qtviz.errors import RendererMissingError

    class _Fake:
        pass

    with pytest.raises(RendererMissingError):
        _figure.build_figure(_Fake(), qv.Theme.light())


# ── event translation (D27) ──────────────────────────────────────────────────
_TRACES = ["scatter-id"]
_SURFACE = "surface-id"


def _t(name, payload):
    return _translate.translate(name, payload, traces=_TRACES, surface_id=_SURFACE)


def test_click_maps_to_pick_event():
    ev = _t("plotly.click", {"points": [{"trace_index": 0, "point_index": 7, "x": 1.5, "y": 2.5}]})
    assert isinstance(ev, qv.PickEvent)
    assert ev.source_id == "scatter-id"
    assert ev.point_index == 7
    assert ev.x == 1.5 and ev.y == 2.5


def test_hover_and_unhover_map_to_hover_event():
    payload = {"points": [{"trace_index": 0, "point_index": 3, "x": 1.0, "y": 2.0}]}
    hov = _t("plotly.hover", payload)
    assert isinstance(hov, qv.HoverEvent) and hov.point_index == 3
    unhov = _t("plotly.unhover", {"points": []})
    assert isinstance(unhov, qv.HoverEvent) and unhov.point_index is None


def test_selection_maps_to_select_event_with_indices_and_bounds():
    payload = {
        "points": [{"point_index": 1}, {"point_index": 3}],
        "range": {"x": [0.0, 5.0], "y": [-1.0, 1.0]},
    }
    ev = _t("plotly.selection", payload)
    assert isinstance(ev, qv.SelectEvent)
    assert ev.indices == [1, 3]
    assert ev.bounds == (0.0, -1.0, 5.0, 1.0)


def test_unknown_message_returns_none():
    assert _t("plotly.attached", {"ok": True}) is None


def test_parse_relayout_both_forms_and_partial():
    full = _translate.parse_relayout(
        {
            "xaxis.range[0]": 0.0, "xaxis.range[1]": 10.0,
            "yaxis.range[0]": -1.0, "yaxis.range[1]": 1.0,
        }
    )
    assert full == ((0.0, 10.0), (-1.0, 1.0))
    # list form, y absent
    assert _translate.parse_relayout({"xaxis.range": [0.0, 10.0]}) == ((0.0, 10.0), None)
    # autorange reset carries no explicit range
    assert _translate.parse_relayout({"xaxis.autorange": True}) == (None, None)
