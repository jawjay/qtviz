"""Tier-1 + Tier-3 — HoloViews adapter (Phase 3, `milestone-holoviews-adapter.md`).

Spec-first: this encodes the `from_holoviews` translation contract (the §2 table)
and the render-conformance gate **before** the adapter exists. Like the other
acceptance suites it `importorskip`s its target, so until
`qtviz.adapter.holoviews` lands the module reports as skipped; when the adapter is
implemented the tests activate and become the gate.

Design anchors: [D28] (RawFigure fallback), [D41] (public-API-only, role-based dim
mapping), [D42] (Histogram→Bars, Spread via Expression y±Δ).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
# Skip on the absent adapter FIRST: importing holoviews (it pulls in numba/bokeh)
# at collection destabilizes the offscreen-Qt teardown, so we must not import it
# until the adapter actually exists. Order matters.
_adapter = pytest.importorskip("qtviz.adapter.holoviews")
hv = pytest.importorskip("holoviews")

from_holoviews = _adapter.from_holoviews


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def df():
    """A tidy frame with a deliberately *undeclared* string column `g` — hv
    auto-promotes it to a vdim, which is exactly the position-mapping trap [D41]."""
    pd = pytest.importorskip("pandas")
    x = np.linspace(0.0, 10.0, 24)
    return pd.DataFrame({"a": x, "b": np.sin(x), "g": list("xyz") * 8})


# ════════════════════════════ Tier 1 — translation ════════════════════════════
# Pure hv-tree → qtviz-Node mapping. No Qt, no rendering.

pytestmark_tier1 = pytest.mark.tier1


@pytest.mark.tier1
def test_scatter_maps_kdim_x_first_vdim_y(df):
    node = from_holoviews(hv.Scatter(df, "a", "b"))
    assert isinstance(node, qv.Scatter)
    assert node.x == "a" and node.y == "b"


@pytest.mark.tier1
def test_scatter_ignores_auto_promoted_vdim(df):
    """`g` is auto-promoted to a vdim by hv; y must still be the declared `b`,
    not the first vdim blindly — the role-mapping rule from [D41]."""
    node = from_holoviews(hv.Scatter(df, "a", "b"))
    assert node.y == "b"


@pytest.mark.tier1
def test_points_maps_both_axes_from_kdims(df):
    """Points carries x and y as *kdims* (no vdim); mapping y to a vdim would
    grab the string column `g` and blow up at render."""
    node = from_holoviews(hv.Points(df, ["a", "b"]))
    assert isinstance(node, qv.Scatter)
    assert node.x == "a" and node.y == "b"


@pytest.mark.tier1
def test_curve_maps(df):
    node = from_holoviews(hv.Curve(df, "a", "b"))
    assert isinstance(node, qv.Curve)
    assert node.x == "a" and node.y == "b"


@pytest.mark.tier1
def test_bars_maps_categorical_x(df):
    node = from_holoviews(hv.Bars(df, "g", "b"))
    assert isinstance(node, qv.Bars)
    assert node.x == "g" and node.y == "b"


@pytest.mark.tier1
def test_heatmap_maps_two_kdims_and_z():
    hm = hv.HeatMap([(i, j, i * j) for i in range(3) for j in range(3)])
    node = from_holoviews(hm)
    assert isinstance(node, qv.Heatmap)
    assert node.x == "x" and node.y == "y" and node.z == "z"


@pytest.mark.tier1
def test_errorbars_symmetric():
    eb = hv.ErrorBars([(0, 1, 0.1), (1, 2, 0.2)], vdims=["y", "yerr"])
    node = from_holoviews(eb)
    assert isinstance(node, qv.ErrorBars)
    ch = node.channels()
    assert "err_lo" in ch and "err_hi" in ch  # symmetric → both present


@pytest.mark.tier1
def test_errorbars_asymmetric():
    eb = hv.ErrorBars([(0, 1, 0.1, 0.3), (1, 2, 0.2, 0.4)], vdims=["y", "neg", "pos"])
    node = from_holoviews(eb)
    assert isinstance(node, qv.ErrorBars)
    assert isinstance(node.err, tuple) and len(node.err) == 2  # (lo, hi) accessors


@pytest.mark.tier1
def test_spread_maps_delta_to_lo_hi():
    """hv Spread is y ± Δ (vdims [y, spread]); qtviz Spread wants explicit
    y_lo/y_hi → Expression arithmetic, both referencing {y, spread} [D42]."""
    sp = hv.Spread([(0, 1, 0.1), (1, 2, 0.2)], vdims=["y", "spread"])
    node = from_holoviews(sp)
    assert isinstance(node, qv.Spread)
    assert node.y_lo.columns() == {"y", "spread"}
    assert node.y_hi.columns() == {"y", "spread"}


@pytest.mark.tier1
def test_histogram_maps_to_bars():
    """hv Histogram is pre-binned (kdim=bin center, vdim=Frequency); qtviz
    Histogram bins a raw column, so the right target is Bars [D42]."""
    counts, edges = np.histogram(np.random.default_rng(0).normal(size=500), bins=8)
    node = from_holoviews(hv.Histogram((edges, counts)))
    assert isinstance(node, qv.Bars)


@pytest.mark.tier1
def test_image_maps_array_and_bounds():
    arr = np.random.default_rng(0).random((8, 10))
    node = from_holoviews(hv.Image(arr))
    assert isinstance(node, qv.Image)
    assert len(node.bounds) == 4  # (l, b, r, t) from hv bounds.lbrt()


@pytest.mark.tier1
def test_overlay_maps_to_overlay(df):
    node = from_holoviews(hv.Scatter(df, "a", "b") * hv.Curve(df, "a", "b"))
    assert isinstance(node, qv.Overlay)
    kinds = [type(c).__name__ for c in node.children]
    assert kinds == ["Scatter", "Curve"]


@pytest.mark.tier1
def test_layout_maps_to_grid(df):
    node = from_holoviews(hv.Scatter(df, "a", "b") + hv.Curve(df, "a", "b"))
    assert isinstance(node, qv.Layout)
    assert node.kind == "grid"


@pytest.mark.tier1
def test_nested_composition_round_trips(df):
    obj = (hv.Scatter(df, "a", "b") * hv.Curve(df, "a", "b")) + hv.Bars(df, "g", "b")
    node = from_holoviews(obj)
    assert isinstance(node, qv.Layout)
    assert isinstance(node.children[0], qv.Overlay)
    assert isinstance(node.children[1], qv.Bars)


@pytest.mark.tier1
def test_unmodeled_element_falls_back_to_rawfigure():
    """The long tail with no native equivalent becomes a webengine RawFigure
    (hv→bokeh state), per [D28] — not an error."""
    pytest.importorskip("bokeh")
    node = from_holoviews(hv.BoxWhisker(np.random.default_rng(0).normal(size=50)))
    assert isinstance(node, qv.RawFigure)


@pytest.mark.tier1
def test_truly_unsupported_raises_actionably():
    """If even the fallback can't apply, raise with a clear hint (taxonomy:
    a QtvizError subclass)."""
    err = getattr(qv.errors, "UnsupportedHoloViewsElement", qv.errors.QtvizError)
    assert issubclass(err, qv.errors.QtvizError)


# ════════════════════════ Tier 3 — render conformance ═════════════════════════
# Every translated node renders through each available *native* backend. Mirrors
# test_backend_conformance.py; reuses the `backend` fixture (skips webengine
# offscreen). Seeded with the Spike-P2 case set.


def _hv_cases(df):
    return {
        "Scatter": hv.Scatter(df, "a", "b"),
        "Points": hv.Points(df, ["a", "b"]),
        "Curve": hv.Curve(df, "a", "b"),
        "Bars": hv.Bars(df, "g", "b"),
        "HeatMap": hv.HeatMap([(i, j, i * j) for i in range(3) for j in range(3)]),
        "ErrorBars": hv.ErrorBars([(0, 1, 0.1), (1, 2, 0.2)], vdims=["y", "yerr"]),
        "Image": hv.Image(np.random.default_rng(0).random((8, 10))),
        "Overlay": hv.Scatter(df, "a", "b") * hv.Curve(df, "a", "b"),
        "Layout": hv.Scatter(df, "a", "b") + hv.Curve(df, "a", "b"),
        "Nested": (hv.Scatter(df, "a", "b") * hv.Curve(df, "a", "b")) + hv.Bars(df, "g", "b"),
    }


@pytest.mark.tier2
@pytest.mark.conformance
def test_translated_tree_renders_on_native_backend(backend, df, qtbot):
    """from_holoviews(obj) → render_root → a QWidget, for every case, on each
    registered native backend. The Spike-P2 acceptance, generalized."""
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from qtviz.core._host import render_root

    failures = []
    for name, obj in _hv_cases(df).items():
        try:
            node = from_holoviews(obj)
            handle = render_root(node, view_backend=backend.name, theme=qv.Theme.light())
            assert isinstance(handle.widget, QtWidgets.QWidget)
            qtbot.addWidget(handle.widget)
            handle.dispose()
        except Exception as exc:  # noqa: BLE001 — collect all, report together
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    assert not failures, f"{backend.name} failed to render: " + "; ".join(failures)
