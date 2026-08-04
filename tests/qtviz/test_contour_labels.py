"""Wave 1.5 — [D117] contour inline labels (`clabel`).

`Contour(labels=True | "fmt")` writes each level's value on its longest
iso-line. Placement is computed once in core — marching-squares polylines,
the longest path's arc-length midpoint, the local tangent angle normalized
to ±90° (text never upside-down), and a short background-colored mask
segment that visually breaks the line under the label. All three backends
draw the existing rotated-Text primitive ([D96]) — deliberately *not* mpl's
native `clabel`, so the backends place labels identically ([D110] over
engine fidelity: the recorded trade-off of this decision).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

# A smooth bump: circular iso-lines around (0, 0).
_gy, _gx = np.mgrid[-2:2:41j, -2:2:41j]
_FIELD = np.exp(-(_gx**2 + _gy**2))
_BOUNDS = (-2.0, -2.0, 2.0, 2.0)


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation():
    from qtviz.errors import ValidationError

    qv.Contour(_FIELD, extent=_BOUNDS, labels=True)
    qv.Contour(_FIELD, extent=_BOUNDS, labels=".2f")
    with pytest.raises(ValidationError):
        qv.Contour(_FIELD, extent=_BOUNDS, labels="{bad}{spec}")


@pytest.mark.tier1
def test_iso_polylines_lie_on_the_level():
    from qtviz.core._stats import iso_polylines

    lines = iso_polylines(_FIELD, 0.5)
    assert lines, "the 0.5 iso-line of a bump must exist"
    # every vertex interpolates the field to ≈ the level
    ny, nx = _FIELD.shape
    for pts in lines:
        assert pts.ndim == 2 and pts.shape[1] == 2
        for cx, cy in pts[:: max(len(pts) // 10, 1)]:
            i, j = int(np.clip(cx, 0, nx - 2)), int(np.clip(cy, 0, ny - 2))
            fx, fy = cx - i, cy - j
            v = (_FIELD[j, i] * (1 - fx) * (1 - fy) + _FIELD[j, i + 1] * fx * (1 - fy)
                 + _FIELD[j + 1, i] * (1 - fx) * fy + _FIELD[j + 1, i + 1] * fx * fy)
            assert abs(v - 0.5) < 0.05
    # the bump's mid iso-line is a closed ring around the origin
    longest = max(lines, key=len)
    assert np.allclose(longest[0], longest[-1])          # closed


@pytest.mark.tier1
def test_label_specs_place_on_lines_with_upright_angles():
    from qtviz.core._stats import contour_label_specs, contour_levels

    lv = contour_levels(_FIELD, 4)
    labels = contour_label_specs(_FIELD, lv, _BOUNDS, spec="auto")
    assert 0 < len(labels) <= len(lv)
    for lb in labels:
        x0, y0, x1, y1 = _BOUNDS
        assert x0 <= lb.x <= x1 and y0 <= lb.y <= y1     # inside the bounds
        assert -90.0 < lb.angle <= 90.0                  # never upside-down
        assert 0.0 <= lb.t <= 1.0
        mx0, my0, mx1, my1 = lb.mask
        assert np.isclose((mx0 + mx1) / 2, lb.x)         # mask centered on label
        assert np.isclose((my0 + my1) / 2, lb.y)
    # 'auto' text is the %g of the level
    texts = {lb.text for lb in labels}
    assert texts <= {format(v, "g") for v in lv}


@pytest.mark.tier1
def test_label_format_spec():
    from qtviz.core._stats import contour_label_specs

    labels = contour_label_specs(_FIELD, np.array([0.5]), _BOUNDS, spec=".2f")
    assert [lb.text for lb in labels] == ["0.50"]


@pytest.mark.tier1
def test_flat_field_yields_no_labels():
    from qtviz.core._stats import contour_label_specs

    labels = contour_label_specs(np.ones((8, 8)), np.array([0.5]), _BOUNDS)
    assert labels == []


@pytest.mark.tier1
def test_webengine_labels_are_rotated_annotations_with_mask():
    from qtviz.backends.webengine import _figure

    el = qv.Contour(_FIELD, extent=_BOUNDS, levels=[0.3, 0.6], labels=True)
    fig = _figure.build_figure(el, qv.Theme.light())
    notes = fig["layout"].get("annotations", [])
    assert len(notes) == 2
    assert {n["text"] for n in notes} == {"0.3", "0.6"}
    assert all("textangle" in n for n in notes)          # Plotly rotates clockwise
    # the mask segments ride a background-colored 9px line trace
    mask = [t for t in fig["data"]
            if t.get("mode") == "lines" and t.get("line", {}).get("width") == 9]
    assert len(mask) == 1


@pytest.mark.tier2
def test_mpl_draws_rotated_label_texts(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Contour(_FIELD, extent=_BOUNDS, levels=[0.3, 0.6], labels=True)
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = handle.axes[0].texts
    assert sorted(t.get_text() for t in texts) == ["0.3", "0.6"]
    assert all(-90.0 < float(t.get_rotation()) <= 90.0
               or float(t.get_rotation()) >= 270.0 for t in texts)


@pytest.mark.tier2
def test_pg_draws_rotated_label_texts(qtbot):
    import pyqtgraph as pg

    el = qv.Contour(_FIELD, extent=_BOUNDS, levels=[0.3, 0.6], labels=True)
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = [it for it in handle.plots[0].items if isinstance(it, pg.TextItem)]
    assert sorted(t.textItem.toPlainText() for t in texts) == ["0.3", "0.6"]


@pytest.mark.tier2
def test_backends_place_labels_identically(qtbot):
    """[D110] payoff: mpl and pg put the same text at the same data point."""
    pytest.importorskip("matplotlib")
    import pyqtgraph as pg

    el = qv.Contour(_FIELD, extent=_BOUNDS, levels=[0.5], labels=True)
    h1 = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h1.widget)
    h2 = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(h2.widget)
    mpl_t = h1.axes[0].texts[0]
    pg_t = next(it for it in h2.plots[0].items if isinstance(it, pg.TextItem))
    assert np.allclose(mpl_t.get_position(), (pg_t.pos().x(), pg_t.pos().y()))
