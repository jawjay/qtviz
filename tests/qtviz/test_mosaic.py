"""Roadmap wave 3, increment 3 ([D108]) — mosaic layouts, ratios, suptitle.

`Layout.mosaic("AAB\\nCCB", A=…, B=…, C=…)` produces per-child
`(row, col, rowspan, colspan)` cells; `grid_geometry` is the single source of
grid shape for every consumer (mpl figure, pg layout, Qt host), which also
makes `rows` honored; `LayoutOptions(width_ratios=, height_ratios=)` size the
tracks; `LayoutOptions.title` — dead since 0.1 — renders as the container
suptitle everywhere.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core import _degrade  # noqa: E402
from qtviz.core.compose import grid_geometry, parse_mosaic  # noqa: E402
from qtviz.errors import QtvizWarning, ValidationError  # noqa: E402

_T = qv.tabular({"x": np.arange(5.0), "y": np.arange(5.0)})


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


def _curve():
    return qv.Curve(_T, x="x", y="y")


# ── parser ────────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_parse_mosaic_spans_and_order():
    cells = parse_mosaic("AAB\nCCB")
    assert list(cells) == ["A", "B", "C"]          # first-appearance order
    assert cells["A"] == (0, 0, 1, 2)
    assert cells["B"] == (0, 2, 2, 1)
    assert cells["C"] == (1, 0, 1, 2)


@pytest.mark.tier1
def test_parse_mosaic_holes_and_semicolons():
    cells = parse_mosaic("A.;.B")                  # `;` rows, `.` holes
    assert cells == {"A": (0, 0, 1, 1), "B": (1, 1, 1, 1)}


@pytest.mark.tier1
@pytest.mark.parametrize("bad", ["", "AB\nA", "AA\nAB", "ABA"])
def test_parse_mosaic_rejects_bad_specs(bad):
    # empty · ragged rows · non-rectangular A · discontiguous A
    with pytest.raises(ValidationError):
        parse_mosaic(bad)


# ── Layout.mosaic + grid_geometry ────────────────────────────────────────────
@pytest.mark.tier1
def test_layout_mosaic_builds_cells():
    lay = qv.Layout.mosaic("AAB\nCCB", A=_curve(), B=_curve(), C=_curve())
    assert lay.cells == ((0, 0, 1, 2), (0, 2, 2, 1), (1, 0, 1, 2))
    cells, nrows, ncols = grid_geometry(lay)
    assert (nrows, ncols) == (2, 3)


@pytest.mark.tier1
def test_layout_mosaic_label_mismatch_raises():
    with pytest.raises(ValidationError, match="missing"):
        qv.Layout.mosaic("AB", A=_curve())
    with pytest.raises(ValidationError, match="unknown"):
        qv.Layout.mosaic("A", A=_curve(), Z=_curve())


@pytest.mark.tier1
def test_mosaic_plus_nests_instead_of_appending():
    lay = qv.Layout.mosaic("AB", A=_curve(), B=_curve())
    outer = lay + _curve()
    assert outer.children[0] is lay                # sealed shape, not flattened


@pytest.mark.tier1
def test_grid_geometry_honors_rows():
    lay = qv.Layout([_curve() for _ in range(4)],
                    options=qv.LayoutOptions(rows=2))
    cells, nrows, ncols = grid_geometry(lay)
    assert (nrows, ncols) == (2, 2)
    assert cells == [(0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)]


@pytest.mark.tier1
def test_ratio_validation():
    with pytest.raises(ValidationError):
        qv.LayoutOptions(width_ratios=[2, -1])
    assert qv.LayoutOptions(width_ratios=[2, 1]).width_ratios == (2.0, 1.0)


# ── matplotlib ────────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_mosaic_spans_ratios_suptitle(qtbot):
    pytest.importorskip("matplotlib")
    b = _backend("matplotlib")
    lay = qv.Layout.mosaic(
        "AAB\nCCB", A=_curve(), B=_curve(), C=_curve(),
        options=qv.LayoutOptions(title="Dash", width_ratios=[1, 1, 2]))
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        handle = b.render(lay, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert not [w for w in caught if issubclass(w.category, QtvizWarning)]
    axes = handle._fig.axes
    spec_a, spec_b = axes[0].get_subplotspec(), axes[1].get_subplotspec()
    assert (spec_a.colspan.start, spec_a.colspan.stop) == (0, 2)   # A spans 2 cols
    assert (spec_b.rowspan.start, spec_b.rowspan.stop) == (0, 2)   # B spans 2 rows
    assert tuple(spec_a.get_gridspec().get_width_ratios()) == (1.0, 1.0, 2.0)
    assert handle._fig._suptitle.get_text() == "Dash"
    handle.dispose()


@pytest.mark.tier2
def test_mpl_rows_honored_without_warning(qtbot):
    pytest.importorskip("matplotlib")
    b = _backend("matplotlib")
    lay = qv.Layout([_curve() for _ in range(4)],
                    options=qv.LayoutOptions(rows=2))
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        handle = b.render(lay, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert not [w for w in caught if issubclass(w.category, QtvizWarning)]
    gs = handle._fig.axes[0].get_subplotspec().get_gridspec()
    assert (gs.nrows, gs.ncols) == (2, 2)
    handle.dispose()


# ── pyqtgraph ─────────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_pg_mosaic_spans_and_title(qtbot):
    b = _backend("pyqtgraph")
    lay = qv.Layout.mosaic(
        "AAB\nCCB", A=_curve(), B=_curve(), C=_curve(),
        options=qv.LayoutOptions(title="Dash", height_ratios=[1, 2]))
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        handle = b.render(lay, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert not [w for w in caught if issubclass(w.category, QtvizWarning)]
    ci = handle.widget.ci
    label = ci.getItem(0, 0)                        # title row spans the top
    assert "Dash" in label.text
    plot_a = ci.getItem(1, 0)                       # grid offset one row down
    assert plot_a is handle.plots[0]
    assert ci.getItem(1, 2) is handle.plots[1]      # B at (0,2) + offset
    handle.dispose()


# ── Qt layout host (mixed-backend grid) ───────────────────────────────────────
@pytest.mark.tier2
def test_host_mosaic_spans_ratios_title(qtbot):
    from PySide6.QtWidgets import QGridLayout, QLabel

    from qtviz.core._host import LayoutHost

    lay = qv.Layout.mosaic(
        "AAB\nCCB",
        A=_curve(), B=qv.Curve(_T, x="x", y="y", backend_hint="matplotlib"),
        C=_curve(),
        options=qv.LayoutOptions(title="Dash", width_ratios=[1, 1, 2]))
    pytest.importorskip("matplotlib")
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        handle = LayoutHost.render(lay, view_backend="pyqtgraph",
                                   theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert not [w for w in caught if issubclass(w.category, QtvizWarning)]
    labels = handle.widget.findChildren(QLabel)
    assert any(lbl.text() == "Dash" for lbl in labels)
    grid = handle.widget.findChild(QGridLayout)
    r, c, rs, cs = grid.getItemPosition(grid.indexOf(handle.children[0].widget))
    assert (r, c, rs, cs) == (0, 0, 1, 2)           # A spans two columns
    r, c, rs, cs = grid.getItemPosition(grid.indexOf(handle.children[1].widget))
    assert (r, c, rs, cs) == (0, 2, 2, 1)           # B spans two rows
    assert grid.columnStretch(2) == 200
    handle.dispose()


# ── end to end through the View ───────────────────────────────────────────────
@pytest.mark.tier2
def test_view_renders_mosaic(qtbot):
    view = qv.View(qv.Layout.mosaic("AB", A=_curve(), B=_curve()),
                   backend="pyqtgraph")
    qtbot.addWidget(view)
    assert view.handle is not None
    assert len(view.handle.plots) == 2
