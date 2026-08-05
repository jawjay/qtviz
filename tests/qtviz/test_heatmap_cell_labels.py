"""Wave 1.4 — [D113] Heatmap cell labels with computed contrast.

One label per aggregated cell, formatted through the [D98]/[D86] vocabulary.
Text, position (cell center), and color are computed once in core: the [D105]
norm maps cell value → ramp color, and `label_color` picks theme foreground or
background by WCAG relative luminance (threshold ≈ 0.45). Backends draw plain
text. A cell-count guard (~400) warns and skips — honest, not silent.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.errors import QtvizWarning, ValidationError  # noqa: E402

_T = {"x": np.array([0.0, 1.0, 0.0, 1.0]),
      "y": np.array([0.0, 0.0, 1.0, 1.0]),
      "z": np.array([0.0, 25.0, 75.0, 100.0])}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


@pytest.mark.tier1
def test_validation():
    qv.Heatmap(_T, x="x", y="y", z="z", annotate="auto")
    qv.Heatmap(_T, x="x", y="y", z="z", annotate=".1f")
    with pytest.raises(ValidationError):
        qv.Heatmap(_T, x="x", y="y", z="z", annotate="{bad}{spec}")


@pytest.mark.tier1
def test_core_labels_text_positions_and_contrast():
    from qtviz.core.encoding import heatmap_cell_labels

    theme = qv.Theme.light()
    xs, ys = np.array([0.0, 1.0]), np.array([0.0, 1.0])
    grid = np.array([[0.0, 25.0], [75.0, np.nan]])
    labels = heatmap_cell_labels(
        xs, ys, grid, spec="auto", colormap="viridis",
        foreground=theme.foreground, background=theme.background)
    assert len(labels) == 3                                # NaN cell skipped
    by_pos = {(lb.x, lb.y): lb for lb in labels}
    assert by_pos[(0.0, 0.0)].text == "0"                  # 'auto' → %g
    assert by_pos[(1.0, 0.0)].text == "25"
    # viridis: low value → dark cell → the *lighter* of fg/bg (light theme: bg)
    assert by_pos[(0.0, 0.0)].color == theme.background
    labels_f = heatmap_cell_labels(
        xs, ys, grid, spec=".1f", colormap="viridis",
        foreground=theme.foreground, background=theme.background)
    assert {lb.text for lb in labels_f} == {"0.0", "25.0", "75.0"}


@pytest.mark.tier1
def test_core_labels_bright_cells_get_dark_text():
    from qtviz.core.encoding import heatmap_cell_labels

    theme = qv.Theme.light()
    labels = heatmap_cell_labels(
        np.array([0.0]), np.array([0.0]), np.array([[1.0]]),
        spec="auto", colormap="viridis", vmin=0.0, vmax=1.0,
        foreground=theme.foreground, background=theme.background)
    # value 1.0 on viridis is bright yellow → the darker of fg/bg (light: fg)
    assert labels[0].color == theme.foreground


@pytest.mark.tier1
def test_core_labels_categorical_axes_use_index_positions():
    from qtviz.core.encoding import heatmap_cell_labels

    theme = qv.Theme.light()
    labels = heatmap_cell_labels(
        np.array(["a", "b"]), np.array(["p", "q"]),
        np.array([[1.0, 2.0], [3.0, 4.0]]),
        spec="auto", colormap="viridis",
        foreground=theme.foreground, background=theme.background)
    assert {(lb.x, lb.y) for lb in labels} == {(0.0, 0.0), (1.0, 0.0),
                                              (0.0, 1.0), (1.0, 1.0)}


@pytest.mark.tier1
def test_cell_count_guard_warns_and_skips():
    from qtviz.core.encoding import heatmap_cell_labels

    theme = qv.Theme.light()
    n = 25
    with pytest.warns(QtvizWarning, match="annotate"):
        out = heatmap_cell_labels(
            np.arange(n, dtype=float), np.arange(n, dtype=float),
            np.ones((n, n)), spec="auto", colormap="viridis",
            foreground=theme.foreground, background=theme.background)
    assert out == []                                       # 625 > 400 → skipped


@pytest.mark.tier1
def test_webengine_cell_labels_are_annotations():
    from qtviz.backends.webengine import _figure

    el = qv.Heatmap(_T, x="x", y="y", z="z", annotate="auto")
    fig = _figure.build_figure(el, qv.Theme.light())
    notes = fig["layout"].get("annotations", [])
    assert len(notes) == 4
    assert {n["text"] for n in notes} == {"0", "25", "75", "100"}
    assert all(n["showarrow"] is False for n in notes)


@pytest.mark.tier2
def test_mpl_draws_cell_label_texts(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Heatmap(_T, x="x", y="y", z="z", annotate="auto")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = [t.get_text() for t in handle.axes[0].texts]
    assert sorted(texts) == ["0", "100", "25", "75"]


@pytest.mark.tier2
def test_pg_draws_cell_label_texts(qtbot):
    import pyqtgraph as pg

    el = qv.Heatmap(_T, x="x", y="y", z="z", annotate="auto")
    handle = _backend("pyqtgraph").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = [it for it in handle.plots[0].items if isinstance(it, pg.TextItem)]
    assert sorted(t.textItem.toPlainText() for t in texts) == ["0", "100", "25", "75"]


@pytest.mark.tier2
def test_no_labels_without_the_option(qtbot):
    pytest.importorskip("matplotlib")
    el = qv.Heatmap(_T, x="x", y="y", z="z")
    handle = _backend("matplotlib").render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    assert len(handle.axes[0].texts) == 0
