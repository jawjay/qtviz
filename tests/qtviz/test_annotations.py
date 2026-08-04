"""0.4 increment 1 — annotation/reference elements ([D70], milestone-0.4 §1).

Four data-less curated elements — `HLine` / `VLine` / `Span` / `Text` — pure
data like every element, composable via `*`, rendered on all three backends
(webengine routes them to Plotly layout shapes/annotations, not traces). A
labeled reference line joins the legend; positions follow the axis scale (R1).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.errors import QtvizWarning, ValidationError  # noqa: E402

_DATA = {"x": np.linspace(1.0, 10.0, 30), "y": np.linspace(1.0, 5.0, 30)}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


# ── Tier-1: the elements are pure data ───────────────────────────────────────
@pytest.mark.tier1
def test_annotation_elements_are_immutable_value_hashed():
    a, b = qv.HLine(3.0, label="limit"), qv.HLine(3.0, label="limit")
    assert a == b and hash(a) == hash(b)          # value identity, id excluded
    assert a != qv.HLine(4.0)
    with pytest.raises(AttributeError):
        a.y = 5.0
    assert a.with_(y=5.0).y == 5.0


@pytest.mark.tier1
def test_annotation_validation():
    with pytest.raises(ValidationError):
        qv.Span(5.0, 2.0)                          # lo must be < hi
    with pytest.raises(ValidationError):
        qv.Span(1.0, 2.0, orient="diagonal")
    with pytest.raises(ValidationError):
        qv.HLine(2.0, alpha=3.0)


@pytest.mark.tier1
def test_annotations_are_data_less_and_resolve_untouched():
    from qtviz.data import resolve_node

    el = qv.VLine(2.0)
    assert el.data is None                         # [D124]: data-less, but `.data` resolves
    assert resolve_node(el) is el                  # passthrough, like RawFigure
    node = resolve_node(qv.Scatter(_DATA, x="x", y="y") * qv.HLine(3.0))
    assert isinstance(node.children[1], qv.HLine)


@pytest.mark.tier1
def test_labeled_reference_line_joins_the_legend_neutrally():
    theme = qv.Theme.light()
    e = qv.HLine(3.0, label="limit").legend_entry(theme, index=2)
    assert e.label == "limit"
    assert e.swatch == theme.foreground            # neutral, NOT palette slot 2
    e2 = qv.HLine(3.0, label="limit", color="#ff0000").legend_entry(theme)
    assert e2.swatch.hex().lower() == "#ff0000"
    assert qv.Span(1.0, 2.0).legend_entry(theme) is None  # unlabeled → no entry


# ── Tier-1: webengine routes to shapes/annotations, never traces ─────────────
@pytest.mark.tier1
def test_webengine_annotations_route_to_layout():
    from qtviz.backends.webengine import _figure

    node = (qv.Scatter(_DATA, x="x", y="y") * qv.HLine(3.0, color="#112233")
            * qv.Span(2.0, 4.0, orient="v") * qv.Text(5.0, 2.5, "peak"))
    fig, source_ids = _figure.build(node, qv.Theme.light())
    assert len(fig["data"]) == 1                   # only the scatter is a trace
    assert len(source_ids) == 1                    # annotations emit no events
    shapes = fig["layout"]["shapes"]
    assert [s["type"] for s in shapes] == ["line", "rect"]
    line, rect = shapes
    assert line["y0"] == line["y1"] == 3.0 and line["xref"] == "paper"
    assert (rect["x0"], rect["x1"]) == (2.0, 4.0) and rect["yref"] == "paper"
    note = fig["layout"]["annotations"][0]
    assert (note["x"], note["y"], note["text"]) == (5.0, 2.5, "peak")


@pytest.mark.tier1
def test_webengine_shape_coords_are_log10_under_log_axis():
    """Plotly wants shape coordinates as log10 values on a log axis."""
    from qtviz.backends.webengine import _figure

    node = qv.Overlay([qv.Scatter(_DATA, x="x", y="y"), qv.VLine(100.0)],
                      options=qv.OverlayOptions(x=qv.AxisSpec(scale="log")))
    fig = _figure.build_figure(node, qv.Theme.light())
    line = fig["layout"]["shapes"][0]
    assert np.isclose(line["x0"], 2.0)             # log10(100)


# ── Tier-2: native rendering ─────────────────────────────────────────────────
def _all_four():
    return (qv.Scatter(_DATA, x="x", y="y")
            * qv.HLine(3.0, label="limit") * qv.VLine(5.0)
            * qv.Span(2.0, 4.0) * qv.Text(5.0, 2.5, "peak"))


@pytest.mark.tier2
def test_pyqtgraph_renders_all_four(qtbot):
    import pyqtgraph as pg

    node = _all_four()
    hline, vline, span, text = node.children[1:]
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    assert isinstance(view.native(hline.id), pg.InfiniteLine)
    assert view.native(hline.id).angle == 0
    assert view.native(vline.id).angle == 90
    assert isinstance(view.native(span.id), pg.LinearRegionItem)
    assert not view.native(span.id).movable        # interactivity via native()
    assert isinstance(view.native(text.id), pg.TextItem)
    # labeled line joined the aggregated legend
    assert [lb.text for _s, lb in view.handle.plots[0]._qtviz_legend.items] == ["limit"]


@pytest.mark.tier2
def test_matplotlib_renders_all_four(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    node = _all_four()
    hline = node.children[1]
    view = qv.View(node, backend="matplotlib")
    qtbot.addWidget(view)
    artist = view.native(hline.id)
    assert artist is not None
    (y0, y1) = artist.get_ydata()
    assert y0 == y1 == 3.0
    assert [t.get_text() for t in view.handle.axes[0].get_legend().get_texts()] == ["limit"]


@pytest.mark.tier2
def test_pyqtgraph_hline_logifies_under_log_y(qtbot):
    node = qv.Overlay([qv.Scatter(_DATA, x="x", y="y"), qv.HLine(100.0)],
                      options=qv.OverlayOptions(y=qv.AxisSpec(scale="log")))
    hline = node.children[1]
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    assert np.isclose(view.native(hline.id).value(), 2.0)   # exponent space (R1)


@pytest.mark.tier2
def test_pyqtgraph_nonpositive_reference_under_log_warns_and_skips(qtbot):
    node = qv.Overlay([qv.Scatter(_DATA, x="x", y="y"), qv.HLine(-1.0)],
                      options=qv.OverlayOptions(y=qv.AxisSpec(scale="log")))
    hline = node.children[1]
    with pytest.warns(QtvizWarning, match="non-positive"):
        view = qv.View(node, backend="pyqtgraph")
        qtbot.addWidget(view)
    assert view.native(hline.id) is None           # dropped, render proceeds
