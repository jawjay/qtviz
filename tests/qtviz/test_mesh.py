"""Roadmap wave 3, increment 1 — `Mesh` ([D106], the pcolormesh analog).

Edges are the canonical contract (`values[j, i]` fills
`x_edges[i]..x_edges[i+1] × y_edges[j]..y_edges[j+1]`); non-uniform spacing
is the point. Shares the [D105] norm surface. pg renders via
`PColorMeshItem` (spiked first, per the roadmap's one load-bearing risk).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_XE = np.array([0.0, 1.0, 3.0, 6.0, 10.0])   # non-uniform
_YE = np.geomspace(1.0, 16.0, 5)             # log-spaced rows
_Z = np.arange(16.0).reshape(4, 4)


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Mesh(_Z, x_edges=_XE, y_edges=_YE)
    with pytest.raises(ValidationError):
        qv.Mesh(_Z, x_edges=[0.0, 1.0, 1.0, 2.0, 3.0], y_edges=_YE)  # not increasing
    with pytest.raises(ValidationError):
        qv.Mesh(_Z, x_edges=[0.0], y_edges=_YE)                      # too short
    with pytest.raises(ValidationError):
        qv.Mesh(_Z, x_edges=_XE, y_edges=_YE, norm="sqrt")
    el = qv.Mesh(np.ones((2, 2)), x_edges=[0, 1, 2], y_edges=[0, 1, 2])
    with pytest.raises(ValidationError):
        el.check_shape(np.ones((3, 3)))                              # shape mismatch


@pytest.mark.tier1
def test_webengine_mesh_edges_as_boundaries():
    from qtviz.backends.webengine import _figure

    el = qv.Mesh(_Z, x_edges=_XE, y_edges=_YE)
    trace = _figure.build_figure(el, qv.Theme.light())["data"][0]
    assert trace["type"] == "heatmap"
    assert len(trace["x"]) == _Z.shape[1] + 1     # one more than z → boundaries
    assert list(trace["x"]) == list(_XE)
    norm = _figure.build_figure(
        qv.Mesh(_Z + 1.0, x_edges=_XE, y_edges=_YE, norm="log"),
        qv.Theme.light())["data"][0]
    assert norm["showscale"] is False             # [D105] honesty carries over


@pytest.mark.tier2
def test_mpl_mesh(qtbot):
    pytest.importorskip("matplotlib")
    from matplotlib.collections import QuadMesh

    el = qv.Mesh(_Z, x_edges=_XE, y_edges=_YE)
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    artist = handle.native(el.id)
    assert isinstance(artist, QuadMesh)
    coords = artist.get_coordinates()
    assert coords.shape == (5, 5, 2)              # (ny+1, nx+1) corners
    assert coords[0, -1, 0] == 10.0               # non-uniform edge preserved


@pytest.mark.tier2
def test_pg_mesh(qtbot):
    import pyqtgraph as pg

    el = qv.Mesh(_Z, x_edges=_XE, y_edges=_YE, vmin=0.0, vmax=20.0)
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    item = handle.native(el.id)
    assert isinstance(item, pg.PColorMeshItem)
    rect = item.boundingRect()
    assert (rect.left(), rect.right()) == (0.0, 10.0)
    assert rect.top() == pytest.approx(1.0) and rect.bottom() == pytest.approx(16.0)


@pytest.mark.tier2
def test_mesh_render_shape_mismatch_raises(qtbot):
    from qtviz.errors import ValidationError

    el = qv.Mesh(np.ones((3, 3)), x_edges=[0, 1, 2], y_edges=[0, 1, 2])  # 2x2 cells
    with pytest.raises(ValidationError, match="shape"):
        _backend("pyqtgraph").render(el, theme=qv.Theme.light())
