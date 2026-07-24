"""0.4 increment 5 — composite export + export knobs ([D72], milestone-0.4 §6),
and the §11 milestone acceptance scenario.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.errors import QtvizWarning  # noqa: E402

_DATA = {"x": np.linspace(1.0, 10.0, 40), "y": np.linspace(1.0, 5.0, 40),
         "cat": np.array(["a", "b"] * 20), "mag": np.linspace(1.0, 1000.0, 40)}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


def _mixed_layout():
    return qv.Layout([
        qv.Scatter(_DATA, x="x", y="y", backend_hint="pyqtgraph"),
        qv.Curve(_DATA, x="x", y="y", backend_hint="matplotlib"),
    ])


# ── composite export ([D72]) ─────────────────────────────────────────────────
@pytest.mark.tier2
def test_composite_export_writes_one_png(qtbot, tmp_path):
    """The [D57]/[D72] edge closes: a mixed-backend layout exports one raster
    instead of raising."""
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(_mixed_layout())
    qtbot.addWidget(view)
    from qtviz.core.backend import CompositeRenderHandle

    assert isinstance(view.handle, CompositeRenderHandle)
    out = view.handle.export("png", tmp_path / "composite.png")
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.tier2
def test_composite_vector_export_still_raises(qtbot, tmp_path):
    """[D58] honesty: no single vector surface across backends — ever."""
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(_mixed_layout())
    qtbot.addWidget(view)
    with pytest.raises(NotImplementedError, match="per-pane"):
        view.handle.export("svg", tmp_path / "composite.svg")


# ── export knobs ([D72]): honored-or-warn per backend ────────────────────────
@pytest.mark.tier2
def test_matplotlib_honors_dpi(qtbot, tmp_path):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(qv.Scatter(_DATA, x="x", y="y"), backend="matplotlib")
    qtbot.addWidget(view)
    small = view.handle.export("png", tmp_path / "s.png", dpi=40)
    big = view.handle.export("png", tmp_path / "b.png", dpi=200)
    assert big.stat().st_size > small.stat().st_size


@pytest.mark.tier2
def test_pyqtgraph_warns_on_dpi_honors_transparent(qtbot, tmp_path):
    view = qv.View(qv.Scatter(_DATA, x="x", y="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    with pytest.warns(QtvizWarning, match="dpi"):
        view.handle.export("png", tmp_path / "p.png", dpi=100)
    out = view.handle.export("png", tmp_path / "t.png", transparent=True)
    assert out.exists() and out.stat().st_size > 0


# ── §11 milestone acceptance ─────────────────────────────────────────────────
@pytest.mark.tier2
def test_milestone_0_4_acceptance(qtbot, tmp_path):
    """The whole 0.4 story at once: reference elements instead of hand-rolled
    bands; box-by-category + grouped bars; true heatmap means; a log-normed
    color key that stays honest; one PNG from a mixed layout."""
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    telemetry = (qv.Curve(_DATA, x="x", y="y", label="signal")
                 * qv.Span(2.0, 4.0, label="tolerance")
                 * qv.HLine(4.5, line_style="dashed", label="alarm"))
    stats = {"v": np.concatenate([np.random.default_rng(1).normal(5, 1, 60),
                                  np.random.default_rng(2).normal(8, 1, 60)]),
             "g": np.array(["a"] * 60 + ["b"] * 60)}
    for backend in ("pyqtgraph", "matplotlib"):
        v1 = qv.View(telemetry, backend=backend)
        qtbot.addWidget(v1)
        v2 = qv.View(qv.BoxPlot(stats, column="v", by="g"), backend=backend)
        qtbot.addWidget(v2)
        v3 = qv.View(qv.Bars({"q": ["Q1", "Q1", "Q2"], "s": [1.0, 2.0, 3.0],
                              "r": ["e", "w", "e"]}, x="q", y="s", group="r"),
                     backend=backend)
        qtbot.addWidget(v3)
        assert v1.handle and v2.handle and v3.handle
    # heatmap true means (not last-wins)
    hm = qv.Heatmap({"x": [0.0, 0.0], "y": [0.0, 0.0], "z": [2.0, 4.0]},
                    x="x", y="y", z="z")
    vh = qv.View(hm, backend="pyqtgraph")
    qtbot.addWidget(vh)
    assert 3.0 in np.asarray(vh.native(hm.id).image).ravel()
    # log-norm honesty: endpoints key, no gradient bar
    vn = qv.View(qv.Scatter(_DATA, x="x", y="y", color_by="mag", color_norm="log"),
                 backend="pyqtgraph")
    qtbot.addWidget(vn)
    assert getattr(vn.handle.plots[0], "_qtviz_cbar", None) is None
    assert vn.handle.plots[0]._qtviz_legend is not None
    # one raster from a mixed-backend layout
    vm = qv.View(_mixed_layout())
    qtbot.addWidget(vm)
    out = vm.handle.export("png", tmp_path / "acceptance.png")
    assert out.exists() and out.stat().st_size > 0
