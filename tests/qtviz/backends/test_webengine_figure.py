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
    """Categorical color_by stays a per-point css list; continuous ([D55] parity)
    is numeric + colorscale so Plotly draws a real colorbar."""
    fig = _figure.build_figure(qv.Scatter(table, x="x", y="y", color_by="cat"), qv.Theme.light())
    color = fig["data"][0]["marker"]["color"]
    assert isinstance(color, list)
    assert len(color) == len(table["x"])
    assert all(c.startswith("rgb(") for c in color)
    cont = _figure.build_figure(qv.Scatter(table, x="x", y="y", color_by="z"), qv.Theme.light())
    marker = cont["data"][0]["marker"]
    assert "colorbar" in marker and "colorscale" in marker
    assert np.asarray(marker["color"]).dtype.kind == "f"  # numeric, Plotly maps it


def test_size_by_scales_per_point_sizes(table):
    fig = _figure.build_figure(qv.Scatter(table, x="x", y="y", size_by="z"), qv.Theme.light())
    # numpy (not a list) so Plotly's base64 typed-array encoder engages (W5.1a)
    size = np.asarray(fig["data"][0]["marker"]["size"])
    assert size.shape == (len(table["x"]),)
    assert size.min() >= 5.0 - 1e-9


def test_layout_carries_theme(table):
    dark = _figure.build_figure(qv.Scatter(table, x="x", y="y"), qv.Theme.dark())["layout"]
    light = _figure.build_figure(qv.Scatter(table, x="x", y="y"), qv.Theme.light())["layout"]
    assert dark["paper_bgcolor"] != light["paper_bgcolor"]
    assert dark["xaxis"]["gridcolor"].startswith("rgb(")


def test_supports_the_data_vocabulary():
    names = {t.__name__ for t in _figure.supported_types()}
    assert names == {
        "Scatter", "Curve", "Bars", "Histogram", "Image", "Heatmap", "ErrorBars", "Spread",
        "BoxPlot", "Violin",
        "Area", "Ecdf", "Pie", "Contour", "Mesh", # parity 3+6, wave 3
    }


def test_every_element_builds_at_least_one_trace(make_elements):
    from qtviz.elements import ANNOTATION_TYPES

    for name, el in make_elements(qv).items():
        fig = _figure.build_figure(el, qv.Theme.light())
        if isinstance(el, ANNOTATION_TYPES):
            # annotations are layout shapes/annotations, never traces ([D70])
            layout = fig["layout"]
            assert layout.get("shapes") or layout.get("annotations"), \
                f"{name} produced no layout shape/annotation"
            continue
        assert fig["data"], f"{name} produced no traces"
        assert all("type" in tr for tr in fig["data"])


def test_element_trace_shapes(make_elements):
    els = make_elements(qv)
    light = qv.Theme.light()
    assert _figure.build_figure(els["Curve"], light)["data"][0]["mode"] == "lines"
    assert _figure.build_figure(els["Bars"], light)["data"][0]["type"] == "bar"
    # pre-binned bar, not a Plotly histogram — shared core binning ([D93])
    assert _figure.build_figure(els["Histogram"], light)["data"][0]["type"] == "bar"
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


def _t(name, payload, traces=_TRACES):
    return _translate.translate(name, payload, traces=traces, surface_id=_SURFACE)


def test_click_maps_to_pick_event():
    evs = _t("plotly.click", {"points": [{"trace_index": 0, "point_index": 7, "x": 1.5, "y": 2.5}]})
    assert len(evs) == 1 and isinstance(evs[0], qv.PickEvent)
    assert evs[0].source_id == "scatter-id"
    assert evs[0].point_index == 7
    assert evs[0].x == 1.5 and evs[0].y == 2.5


def test_hover_and_unhover_map_to_hover_event():
    payload = {"points": [{"trace_index": 0, "point_index": 3, "x": 1.0, "y": 2.0}]}
    hov = _t("plotly.hover", payload)
    assert len(hov) == 1 and isinstance(hov[0], qv.HoverEvent) and hov[0].point_index == 3
    unhov = _t("plotly.unhover", {"points": []})
    assert len(unhov) == 1 and unhov[0].point_index is None


def test_single_trace_selection_emits_one_select_event():
    payload = {
        "points": [{"trace_index": 0, "point_index": 1}, {"trace_index": 0, "point_index": 3}],
        "range": {"x": [0.0, 5.0], "y": [-1.0, 1.0]},
    }
    evs = _t("plotly.selection", payload)
    assert len(evs) == 1 and isinstance(evs[0], qv.SelectEvent)
    assert evs[0].source_id == "scatter-id"
    assert evs[0].indices == [1, 3]
    assert evs[0].bounds == (0.0, -1.0, 5.0, 1.0)


def test_multi_trace_selection_emits_one_event_per_source(table):
    # an Overlay → two traces "a" and "b"; a brush selecting points from both
    # yields one SelectEvent per source element (matches native pyqtgraph).
    payload = {
        "points": [
            {"trace_index": 0, "point_index": 2},
            {"trace_index": 1, "point_index": 5},
            {"trace_index": 1, "point_index": 9},
        ],
        "range": {"x": [0.0, 1.0], "y": [0.0, 1.0]},
    }
    evs = _t("plotly.selection", payload, traces=["a", "b"])
    by_src = {e.source_id: e.indices for e in evs}
    assert by_src == {"a": [2], "b": [5, 9]}


def test_unknown_message_returns_empty():
    assert _t("plotly.attached", {"ok": True}) == []


# A 3-D surface / heatmap / contour point is a multi-dim [row, col] cell — Plotly
# sends point_index as a list, which has no single row identity (regression: this
# crashed int(point_index)).
_SURFACE_PT = {"points": [{"trace_index": 0, "point_index": [3, 5], "x": 1.0, "y": 2.0}]}


def test_surface_hover_multidim_index_degrades_to_none():
    evs = _t("plotly.hover", _SURFACE_PT)
    assert len(evs) == 1 and isinstance(evs[0], qv.HoverEvent)
    assert evs[0].point_index is None
    assert evs[0].x == 1.0 and evs[0].y == 2.0


def test_surface_click_multidim_index_uses_sentinel():
    evs = _t("plotly.click", _SURFACE_PT)
    assert len(evs) == 1 and isinstance(evs[0], qv.PickEvent)
    assert evs[0].point_index == -1


def test_selection_skips_multidim_indices():
    payload = {
        "points": [{"trace_index": 0, "point_index": [1, 2]}, {"trace_index": 0, "point_index": 4}],
        "range": {"x": [0.0, 5.0], "y": [0.0, 5.0]},
    }
    evs = _t("plotly.selection", payload)
    assert evs[0].indices == [4]  # only the scalar index survives


def test_categorical_coordinate_does_not_crash():
    import math

    # a Bars hover sends x as the category label string, not a number
    evs = _t("plotly.hover", {"points": [{"trace_index": 0, "point_index": 5, "x": "d", "y": 3.0}]})
    assert len(evs) == 1 and isinstance(evs[0], qv.HoverEvent)
    assert math.isnan(evs[0].x)  # non-numeric category → NaN, not a ValueError
    assert evs[0].y == 3.0


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


# ── Bokeh / HoloViews event translation (W3b) ─────────────────────────────────
def test_bokeh_tap_maps_to_tap_event():
    evs = _t("bokeh.tap", {"x": 1.5, "y": 2.5, "sx": 10, "sy": 20})
    assert len(evs) == 1 and isinstance(evs[0], qv.TapEvent)
    assert evs[0].source_id == "surface-id"  # tap is surface-level
    assert evs[0].x == 1.5 and evs[0].y == 2.5


def test_bokeh_rect_selection_maps_to_select_with_bounds():
    geom = {"type": "rect", "x0": 0.0, "y0": 1.0, "x1": 5.0, "y1": 6.0}
    evs = _t("bokeh.selection", {"geometry": geom})
    assert len(evs) == 1 and isinstance(evs[0], qv.SelectEvent)
    assert evs[0].source_id == "scatter-id"  # the figure's own id
    assert evs[0].indices == []  # a SelectionGeometry carries the region, not row indices
    assert evs[0].bounds == (0.0, 1.0, 5.0, 6.0)


def test_bokeh_poly_selection_bounds_is_bounding_box():
    geom = {"type": "poly", "x": [0.0, 2.0, 1.0], "y": [0.0, 1.0, 3.0]}
    evs = _t("bokeh.selection", {"geometry": geom})
    assert evs[0].bounds == (0.0, 0.0, 2.0, 3.0)


def test_bokeh_double_tap_has_no_qtviz_equivalent():
    assert _t("bokeh.double_tap", {"x": 1.0, "y": 2.0}) == []


def test_parse_bokeh_ranges():
    full = _translate.parse_bokeh_ranges({"x0": 0.0, "x1": 10.0, "y0": -1.0, "y1": 1.0})
    assert full == ((0.0, 10.0), (-1.0, 1.0))
    assert _translate.parse_bokeh_ranges({"x0": 0.0, "x1": 10.0}) == ((0.0, 10.0), None)
    assert _translate.parse_bokeh_ranges({}) == (None, None)
