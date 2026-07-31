"""Roadmap wave 1, increment 1 — the annotation vocabulary ([D96]/[D97]).

`Arrow` (the pointing half of `annotate`), `Text` growing `rotation` /
`anchor_v` / `frame`, and the shape annotations `Rect` / `Ellipse` /
`Polygon` — all [D70]-class: pure data, theme-foreground default, drawn as
layout chrome on webengine, palette-slot-free in overlays.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_T = {"x": [0.0, 1.0, 2.0, 3.0], "y": [0.0, 1.0, 0.5, 1.5]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1: construction ─────────────────────────────────────────────────────
@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Arrow(0, 0, 1, 1, head="both")
    qv.Rect(0, 0, 1, 1, fill=True)
    qv.Ellipse(0, 0, 2, 1, angle=30)
    qv.Polygon([(0, 0), (1, 0), (0.5, 1)])
    qv.Text(0, 0, "t", rotation=45, anchor_v="top", frame=True)
    with pytest.raises(ValidationError):
        qv.Arrow(0, 0, 1, 1, head="start")
    with pytest.raises(ValidationError):
        qv.Rect(1, 0, 0, 1)  # x0 must be < x1
    with pytest.raises(ValidationError):
        qv.Ellipse(0, 0, -1, 1)
    with pytest.raises(ValidationError):
        qv.Polygon([(0, 0), (1, 1)])  # < 3 points
    with pytest.raises(ValidationError):
        qv.Text(0, 0, "t", anchor_v="above")


@pytest.mark.tier1
def test_annotations_are_chrome():
    """New types join ANNOTATION_TYPES: no palette slot, no data ref."""
    from qtviz.core.compose import series_index_map
    from qtviz.elements import ANNOTATION_TYPES

    for t in (qv.Arrow, qv.Rect, qv.Ellipse, qv.Polygon):
        assert t in ANNOTATION_TYPES
    children = (qv.Curve(_T, x="x", y="y"), qv.Arrow(0, 0, 1, 1),
                qv.Rect(0, 0, 1, 1), qv.Curve(_T, x="x", y="y"))
    assert series_index_map(children) == [0, 0, 0, 1]


@pytest.mark.tier1
def test_core_ellipse_geometry():
    from qtviz.core._geometry import ellipse_points

    pts = ellipse_points(2.0, 3.0, 1.0, 0.5, angle=0.0, n=8)
    assert pts.shape == (9, 2)                    # closed
    assert np.allclose(pts[0], pts[-1])
    assert np.allclose(pts[0], [3.0, 3.0])        # cx + rx at t=0
    rot = ellipse_points(0.0, 0.0, 1.0, 1.0, angle=45.0, n=8)
    assert np.allclose(np.hypot(rot[:, 0], rot[:, 1]), 1.0)  # circle invariant


# ── tier 1: webengine (pure figure spec) ─────────────────────────────────────
@pytest.mark.tier1
def test_webengine_arrow_annotation():
    from qtviz.backends.webengine import _figure

    node = qv.Curve(_T, x="x", y="y") * qv.Arrow(0.5, 0.2, 2.0, 1.0, head="both")
    layout = _figure.build_figure(node, qv.Theme.light())["layout"]
    (note,) = layout["annotations"]
    assert note["showarrow"] is True
    assert (note["x"], note["y"], note["ax"], note["ay"]) == (2.0, 1.0, 0.5, 0.2)
    assert note["axref"] == "x" and note["arrowside"] == "end+start"


@pytest.mark.tier1
def test_webengine_shapes():
    from qtviz.backends.webengine import _figure

    node = (qv.Curve(_T, x="x", y="y")
            * qv.Rect(0.5, 0.0, 1.5, 1.0, fill=True)
            * qv.Ellipse(2.0, 0.5, 0.5, 0.25)
            * qv.Polygon([(0, 0), (1, 0), (0.5, 1)]))
    shapes = _figure.build_figure(node, qv.Theme.light())["layout"]["shapes"]
    kinds = sorted(s["type"] for s in shapes)
    assert kinds == ["path", "path", "rect"]
    rect = next(s for s in shapes if s["type"] == "rect")
    assert "fillcolor" in rect and rect["x0"] == 0.5
    paths = [s for s in shapes if s["type"] == "path"]
    assert all(s["path"].startswith("M ") and s["path"].endswith("Z") for s in paths)
    assert all("fillcolor" not in s for s in paths)  # outline-only defaults


@pytest.mark.tier1
def test_webengine_text_rotation_frame():
    from qtviz.backends.webengine import _figure

    node = qv.Curve(_T, x="x", y="y") * qv.Text(
        1.0, 1.0, "note", rotation=30.0, anchor_v="top", frame=True)
    (note,) = _figure.build_figure(node, qv.Theme.light())["layout"]["annotations"]
    assert note["textangle"] == -30.0             # Plotly rotates clockwise
    assert note["yanchor"] == "top"
    assert "bordercolor" in note and "bgcolor" in note


@pytest.mark.tier1
def test_webengine_shape_coords_on_time_axis():
    """Annotation coordinates follow the axis to epoch-ms on a date axis
    ([D94] seam — previously they landed in 1970)."""
    from qtviz.backends.webengine import _figure

    days = np.arange("2026-01-01", "2026-01-11",
                     dtype="datetime64[D]").astype("datetime64[ns]")
    epoch0 = 1_767_225_600.0
    node = (qv.Curve({"d": days, "v": np.arange(10.0)}, x="d", y="v")
            * qv.VLine(epoch0 + 86400.0))
    (shape,) = _figure.build_figure(node, qv.Theme.light())["layout"]["shapes"]
    assert shape["x0"] == (epoch0 + 86400.0) * 1000.0


# ── tier 2: matplotlib ───────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_annotation_wave(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib import patches

    arrow = qv.Arrow(0.5, 0.2, 2.0, 1.0)
    rect = qv.Rect(0.5, 0.0, 1.5, 1.0, fill=True, alpha=0.3)
    ell = qv.Ellipse(2.0, 0.5, 0.5, 0.25, angle=20.0)
    poly = qv.Polygon([(0, 0), (1, 0), (0.5, 1)])
    text = qv.Text(1.0, 1.2, "note", rotation=45.0, anchor_v="bottom", frame=True)
    node = qv.Curve(_T, x="x", y="y") * arrow * rect * ell * poly * text
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert isinstance(handle.native(rect.id), patches.Rectangle)
    assert handle.native(rect.id).get_alpha() == 0.3
    assert isinstance(handle.native(ell.id), patches.Ellipse)
    assert handle.native(ell.id).angle == 20.0
    assert isinstance(handle.native(poly.id), patches.Polygon)
    t = handle.native(text.id)
    assert t.get_rotation() == 45.0
    assert t.get_va() == "bottom"
    assert t.get_bbox_patch() is not None
    assert handle.native(arrow.id).arrow_patch is not None


@pytest.mark.tier2
def test_mpl_shapes_dont_break_autoscale(qtbot):
    """Patches join dataLim by design (they're data-space), but the P1 brush
    guard must still keep the selector artifact out."""
    pytest.importorskip("matplotlib")
    node = (qv.Scatter({"x": [100.0, 110.0], "y": [100.0, 110.0]}, x="x", y="y")
            * qv.Rect(101.0, 101.0, 105.0, 105.0))
    handle = _backend("matplotlib").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    x0, _x1 = handle.axes[0].dataLim.intervalx
    assert x0 >= 100.0


# ── tier 2: pyqtgraph ────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_annotation_wave(qtbot):
    import pyqtgraph as pg
    from PySide6.QtWidgets import QGraphicsPathItem

    arrow = qv.Arrow(0.5, 0.2, 2.0, 1.0, head="both")
    ell = qv.Ellipse(2.0, 0.5, 0.5, 0.25)
    text = qv.Text(1.0, 1.2, "note", rotation=45.0, frame=True)
    node = qv.Curve(_T, x="x", y="y") * arrow * ell * text
    handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    items = handle.native(arrow.id)
    assert isinstance(items[0], pg.PlotCurveItem)         # shaft
    assert sum(isinstance(i, pg.ArrowItem) for i in items) == 2
    assert isinstance(handle.native(ell.id), QGraphicsPathItem)
    assert handle.native(text.id).angle == 45.0


@pytest.mark.tier2
def test_pg_shape_drops_under_log_with_nonpositive(qtbot):
    """Data-space rule under log: a shape crossing zero can't transform —
    it drops (logify warns) instead of drawing garbage."""
    node = qv.Overlay(
        [qv.Curve({"x": [1.0, 10.0], "y": [1.0, 10.0]}, x="x", y="y"),
         qv.Rect(-1.0, 1.0, 5.0, 5.0)],
        options=qv.OverlayOptions(x=qv.AxisSpec(scale="log")),
    )
    with pytest.warns(Warning):
        handle = _backend("pyqtgraph").render(node, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    rect_el = node.children[1]
    assert handle.native(rect_el.id) is None
