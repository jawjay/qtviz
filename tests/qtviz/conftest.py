"""Shared fixtures for the qtviz acceptance benchmarks.

These suites are **spec-first**: they encode the contracts in `design/spec.md`
and `design/development-plan.md` and are written *before* the implementation.
Until the `qtviz` package exists each module `pytest.importorskip("qtviz")`s
and the suite reports as skipped; as each component lands its tests activate
and become the gate.

Assumed public API (the target the implementation is written against — see
development-plan §6 "Public API surface"):

    qtviz                  Scatter Curve Bars Image Heatmap Histogram
                           ErrorBars Spread · Overlay Layout · View · Theme
                           Color Palette Options · palettes
                           set_default_backend set_backend_priority
    qtviz.data             as_data_ref register_data_adapter list_data_adapters
                           DataRef TabularRef GriddedRef
    qtviz.backends         list_available register unregister get
    qtviz.core.compose     negotiate auto_negotiate
    qtviz.errors           IncompatibleOverlayError UnsupportedElementError
                           NoBackendForError
    qtviz.threading        require_gui_thread run_on_gui Worker is_gui_thread

If the implementation names something differently, adjust the import here and
in the affected module — that is the single source of these assumptions.
"""

from __future__ import annotations

import os

# Headless Qt: every Tier-2 test runs offscreen unless the caller overrides.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

N = 200  # rows in the canonical sample table


# ── raw data fixtures ────────────────────────────────────────────────────────
@pytest.fixture
def table() -> dict[str, np.ndarray]:
    """Canonical tabular fixture as a dict of 1-D numpy columns — the form the
    `dict` adapter handles directly and the reference all other tabular
    encodings (pandas, arrow) must reproduce byte-for-byte."""
    rng = np.random.default_rng(0)
    x = np.linspace(0.0, 10.0, N)
    y = np.sin(x) + rng.normal(0, 0.05, N)
    return {
        "x": x,
        "y": y,
        "y_lo": y - 0.1,
        "y_hi": y + 0.1,
        "err": np.full(N, 0.1),
        "z": np.cos(x),
        "cat": np.array(["a", "b", "c", "d"] * (N // 4)),
    }


@pytest.fixture
def grid() -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Canonical gridded fixture: a 2-D value array + (xmin, ymin, xmax, ymax)."""
    values = np.outer(np.hanning(20), np.hanning(30))
    return values, (0.0, 0.0, 30.0, 20.0)


# ── factory fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def make_elements(table, grid):
    """Returns `build(qv) -> dict[name, Element]` for all 8 Phase-1 elements,
    constructed against the sample fixtures. Used by the backend conformance
    suite to iterate every element a backend claims to support."""
    values, bounds = grid

    def build(qv) -> dict:
        return {
            "Scatter": qv.Scatter(table, x="x", y="y"),
            "Curve": qv.Curve(table, x="x", y="y"),
            "Bars": qv.Bars(table, x="cat", y="y"),
            "Histogram": qv.Histogram(table, column="y"),
            "ErrorBars": qv.ErrorBars(table, x="x", y="y", err="err"),
            "Spread": qv.Spread(table, x="x", y_lo="y_lo", y_hi="y_hi"),
            "Image": qv.Image(values, bounds=bounds),
            "Heatmap": qv.Heatmap(table, x="x", y="y", z="z"),
            # annotation / reference elements ([D70], 0.4)
            "HLine": qv.HLine(0.5),
            "VLine": qv.VLine(5.0),
            "Span": qv.Span(0.2, 0.8),
            "Text": qv.Text(5.0, 0.5, "note"),
            # statistical elements ([D67], 0.4)
            "BoxPlot": qv.BoxPlot(table, column="y"),
            "Violin": qv.Violin(table, column="y"),
            # composition vocabulary (parity increment 3, [D84b]/[D90]/[D91])
            "Area": qv.Area(table, x="x", y="y"),
            "Ecdf": qv.Ecdf(table, column="y"),
            "Contour": qv.Contour(values, bounds=bounds),
            "Pie": qv.Pie({"v": [3.0, 2.0, 1.0], "l": ["a", "b", "c"]},
                          values="v", labels="l"),
        }

    return build


@pytest.fixture
def make_stub_backend():
    """Returns a factory for fake backends used by the *pure* negotiation
    tests. A stub only needs the surface `negotiate`/`auto_negotiate` read:
    a name, a `supports(type)` predicate, and a `capabilities` object exposing
    `max_recommended_points`. No Qt, no rendering."""
    from types import SimpleNamespace

    def factory(name: str, supports: set, *, max_points: int = 1_000_000):
        return SimpleNamespace(
            name=name,
            capabilities=SimpleNamespace(max_recommended_points=max_points),
            supports=lambda t, _s=supports: t.__name__ in _s or t in _s,
            renderers=SimpleNamespace(types=lambda _s=supports: set(_s)),
            # round out the Backend surface so a runtime-checkable Protocol /
            # registry accepts the stub even though it never renders.
            render=lambda *a, **k: None,
            can_host=lambda kind: False,
        )

    return factory


# ── parametrization over what is actually registered ─────────────────────────
def _available_backend_names() -> list[str]:
    try:
        import qtviz.backends as B

        names = list(B.list_available())
        # list_available may yield names or instances; normalize to names.
        return [getattr(n, "name", n) for n in names]
    except Exception:
        return []


def _tabular_encodings() -> list[str]:
    enc = ["dict"]
    for lib, name in (("pandas", "pandas"), ("pyarrow", "arrow")):
        try:
            __import__(lib)
            enc.append(name)
        except Exception:
            pass
    return enc


@pytest.fixture(params=_available_backend_names())
def backend(request):
    """One registered backend per param. Empty (suite skips) until a backend
    is registered — at which point the conformance suite covers it."""
    import contextlib

    import qtviz.backends as B

    name = request.param
    instance = None
    with contextlib.suppress(Exception):
        instance = B.get(name)
    if instance is None:
        registry = {getattr(b, "name", b): b for b in B.list_available()}
        instance = registry.get(name)
    if instance is None:
        pytest.skip(f"cannot resolve backend instance for {name!r}")

    # A display-bound backend (webengine) can't complete its live render path
    # under offscreen Qt; its full conformance run is W2 on a real display.
    if (
        getattr(instance, "requires_display", False)
        and os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        and os.environ.get("QTVIZ_WEBENGINE_GUI") != "1"
    ):
        pytest.skip(f"{name} needs a display; offscreen (set QTVIZ_WEBENGINE_GUI=1 to force)")
    return instance


@pytest.fixture(params=_tabular_encodings())
def tabular_encoding(request, table):
    """The same logical table encoded as dict / pandas DataFrame / Arrow Table,
    so the adapter conformance suite can assert identical `series()` output
    across every installed tabular container."""
    enc = request.param
    if enc == "dict":
        return enc, dict(table)
    if enc == "pandas":
        pd = pytest.importorskip("pandas")
        return enc, pd.DataFrame(table)
    if enc == "arrow":
        pa = pytest.importorskip("pyarrow")
        return enc, pa.table(table)
    raise AssertionError(enc)
