"""Parity program increment 6 — `Contour` ([D89]).

Iso-lines over the `Image` data contract. Level values are computed once in
core (`contour_levels`) so every backend draws the same lines; `filled` fills
on matplotlib/webengine and warns on pyqtgraph.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_VALUES = np.outer(np.hanning(12), np.hanning(16))
_BOUNDS = (0.0, 0.0, 8.0, 6.0)


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_contour_validation():
    from qtviz.errors import ValidationError

    qv.Contour(_VALUES, bounds=_BOUNDS, levels=5)
    qv.Contour(_VALUES, bounds=_BOUNDS, levels=[0.2, 0.5, 0.8])
    with pytest.raises(ValidationError):
        qv.Contour(_VALUES, bounds=_BOUNDS, levels=0)
    with pytest.raises(ValidationError):
        qv.Contour(_VALUES, bounds=_BOUNDS, levels=[])
    with pytest.raises(TypeError):
        qv.Contour({"x": [1.0]}, bounds=_BOUNDS)  # tabular data → gridded required


@pytest.mark.tier1
def test_core_contour_levels_shared():
    from qtviz.core._stats import contour_levels

    lv = contour_levels(_VALUES, 4)
    assert len(lv) == 4
    assert lv[0] > _VALUES.min() and lv[-1] < _VALUES.max()  # interior levels
    explicit = contour_levels(_VALUES, [0.8, 0.2])
    assert list(explicit) == [0.2, 0.8]  # sorted passthrough


@pytest.mark.tier1
def test_webengine_contour_trace():
    from qtviz.backends.webengine import _figure
    from qtviz.core._stats import contour_levels

    el = qv.Contour(_VALUES, bounds=_BOUNDS, levels=4, colormap="plasma")
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    lv = contour_levels(_VALUES, 4)
    assert trace["type"] == "contour"
    assert trace["contours"]["coloring"] == "lines"
    assert trace["contours"]["start"] == pytest.approx(float(lv[0]))
    assert trace["contours"]["end"] == pytest.approx(float(lv[-1]))
    assert trace["colorscale"] == "Plasma"
    assert trace["showscale"] is False
    filled = _figure.build_figure(
        qv.Contour(_VALUES, bounds=_BOUNDS, filled=True), qv.Theme.light())["data"][0]
    assert filled["contours"]["coloring"] == "fill" and filled["showscale"] is True


@pytest.mark.tier2
def test_mpl_contour_lines_and_filled(qtbot):
    pytest.importorskip("matplotlib")
    from qtviz.core._stats import contour_levels

    b = _backend("matplotlib")
    el = qv.Contour(_VALUES, bounds=_BOUNDS, levels=4)
    handle = b.render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    cs = handle.native(el.id)
    assert np.allclose(cs.levels, contour_levels(_VALUES, 4))
    el2 = qv.Contour(_VALUES, bounds=_BOUNDS, levels=4, filled=True)
    handle2 = b.render(el2, theme=qv.Theme.light())
    qtbot.addWidget(handle2.widget)
    assert handle2.native(el2.id).filled


@pytest.mark.tier2
def test_pg_contour_isocurves_mapped_to_bounds(qtbot):
    import pyqtgraph as pg

    el = qv.Contour(_VALUES, bounds=_BOUNDS, levels=4)
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    items = handle.native(el.id)
    assert len(items) == 4 and all(isinstance(i, pg.IsocurveItem) for i in items)
    x0, y0, x1, y1 = _BOUNDS
    for item in items:
        rect = item.mapRectToParent(item.boundingRect())
        assert rect.left() >= x0 - 1e-6 and rect.right() <= x1 + 1e-6
        assert rect.top() >= y0 - 1e-6 and rect.bottom() <= y1 + 1e-6


@pytest.mark.tier2
def test_pg_contour_filled_warns(qtbot):
    from qtviz.core import _degrade
    from qtviz.errors import QtvizWarning

    _degrade.reset()
    el = qv.Contour(_VALUES, bounds=_BOUNDS, filled=True)
    with pytest.warns(QtvizWarning, match="'filled'"):
        handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
