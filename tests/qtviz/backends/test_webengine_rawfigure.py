"""W3a — RawFigure passthrough: detection, negotiation, and Overlay rejection.

All headless (no Qt / WebEngine): construction, library detection, that a
RawFigure negotiates only to webengine, and that it can't be overlaid. The live
render of a raw figure is display-gated (test_webengine_render.py).
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")

from qtviz.elements.raw_figure import _detect_kind  # noqa: E402

pytestmark = pytest.mark.tier1


def _stub(module: str):
    cls = type("Fig", (), {})
    cls.__module__ = module
    return cls()


def test_detect_kind_from_module_path():
    assert _detect_kind(_stub("plotly.graph_objs._figure")) == "plotly"
    assert _detect_kind(_stub("bokeh.plotting._figure")) == "bokeh"
    assert _detect_kind(_stub("holoviews.element.chart")) == "holoviews"


def test_detect_kind_unknown_raises():
    with pytest.raises(TypeError):
        _detect_kind(_stub("matplotlib.figure"))


def test_rawfigure_detects_real_plotly_figure():
    go = pytest.importorskip("plotly.graph_objects")
    rf = qv.RawFigure(go.Figure())
    assert rf.kind == "plotly"


def test_rawfigure_explicit_kind_overrides_detection():
    rf = qv.RawFigure(object(), kind="bokeh")
    assert rf.kind == "bokeh"


def test_rawfigure_invalid_kind_raises():
    with pytest.raises(ValueError):
        qv.RawFigure(object(), kind="matplotlib")


def test_rawfigure_undetectable_raises():
    with pytest.raises(TypeError):
        qv.RawFigure(object())


def test_rawfigure_fields_round_trip():
    rf = qv.RawFigure(object(), kind="plotly")
    clone = type(rf)(**rf._fields())  # the Immutable reconstruct contract
    assert clone.kind == "plotly" and clone == rf


def test_rawfigure_negotiates_only_to_webengine():
    import qtviz.backends as B

    rf = qv.RawFigure(object(), kind="plotly")
    assert qv.negotiate(rf, "auto") == "webengine"
    assert B.get("webengine").supports(qv.RawFigure)
    assert not B.get("pyqtgraph").supports(qv.RawFigure)


def test_rawfigure_cannot_be_overlaid(table):
    from qtviz.backends.webengine import _figure
    from qtviz.errors import IncompatibleOverlayError

    overlay = qv.Scatter(table, x="x", y="y") * qv.RawFigure(object(), kind="plotly")
    with pytest.raises(IncompatibleOverlayError):
        _figure.build(overlay, qv.Theme.light())
