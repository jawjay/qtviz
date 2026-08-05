"""Tier-1 — backend negotiation (spec §3.1–§3.3), pure, no Qt.

Negotiation resolves a backend per node from hints + capabilities, using only
the registry's `supports()` + priority. Tested against *stub* backends so the
logic is exercised with no rendering and no QApplication.

Stubs (disjoint coverage, to exercise Overlay coherence both ways):
    alpha → {Scatter, Curve}   beta → {Scatter, Bars}   gamma → {Curve}
    priority [alpha, beta, gamma], default alpha
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")
compose = pytest.importorskip("qtviz.core.compose")
errors = pytest.importorskip("qtviz.errors")

pytestmark = pytest.mark.tier1


@pytest.fixture
def registry(make_stub_backend, table):
    """Install a clean registry with only the three stub backends — real
    backends (pyqtgraph) must not leak into the pure negotiation tests — then
    restore the prior registry state afterward."""
    import qtviz.backends as B

    stubs = [
        make_stub_backend("alpha", {"Scatter", "Curve"}),
        make_stub_backend("beta", {"Scatter", "Bars"}),
        make_stub_backend("gamma", {"Curve"}),
    ]
    saved = (dict(B._REGISTRY), list(B._PRIORITY), B._DEFAULT)
    try:
        B._REGISTRY.clear()
        B._PRIORITY.clear()
        for s in stubs:
            B.register(s)
        qv.backends.set_backend_priority(["alpha", "beta", "gamma"])
        qv.set_default_backend("alpha")
    except AttributeError as e:
        pytest.skip(f"registry API not available yet: {e}")
    yield compose
    B._REGISTRY.clear()
    B._REGISTRY.update(saved[0])
    B._PRIORITY[:] = saved[1]
    B._DEFAULT = saved[2]


def _scatter(**kw):
    return qv.Scatter({"x": [0, 1], "y": [0, 1]}, x="x", y="y", **kw)


def _curve(**kw):
    return qv.Curve({"x": [0, 1], "y": [0, 1]}, x="x", y="y", **kw)


def _bars(**kw):
    return qv.Bars({"x": ["a", "b"], "y": [0, 1]}, x="x", y="y", **kw)


# ── precedence: Element > Composition > View > Global (§3.1) ──────────────────
def test_element_hint_beats_view_backend(registry):
    assert registry.negotiate(_scatter(backend_hint="beta"), "alpha") == "beta"


def test_composition_hint_applies_to_unhinted_children(registry):
    ov = qv.Overlay([_scatter()], backend_hint="beta")
    assert registry.negotiate(ov, "alpha") == "beta"


def test_view_backend_used_without_hints(registry):
    assert registry.negotiate(_scatter(), "beta") == "beta"


def test_global_default_is_last_resort(registry):
    assert registry.negotiate(_scatter(), None) == "alpha"


# ── Overlay coherence (§2.3, §3.2) ───────────────────────────────────────────
def test_overlay_same_backend_ok(registry):
    assert registry.negotiate(qv.Overlay([_scatter(), _curve()]), "alpha") == "alpha"


def test_overlay_conflicting_hints_raise(registry):
    ov = qv.Overlay([_scatter(backend_hint="alpha"), _scatter(backend_hint="beta")])
    with pytest.raises(errors.IncompatibleOverlayError):
        registry.negotiate(ov, "alpha")


def test_layout_children_may_differ(registry):
    lay = qv.Layout([_scatter(backend_hint="alpha"), _bars(backend_hint="beta")])
    registry.negotiate(lay, "alpha")  # must not raise


def test_unsupported_element_on_backend_raises(registry):
    with pytest.raises(errors.UnsupportedElementError):
        registry.negotiate(_curve(backend_hint="beta"), "beta")  # beta lacks Curve


# ── auto mode (§3.3, incl. the D4 supports-all-children fix) ──────────────────
def test_auto_picks_highest_priority_supporting_backend(registry):
    assert registry.auto_negotiate(_scatter()) == "alpha"  # alpha,beta → alpha
    assert registry.auto_negotiate(_curve()) == "alpha"    # alpha,gamma → alpha


def test_auto_overlay_collapses_to_common_backend(registry):
    assert registry.auto_negotiate(qv.Overlay([_scatter(), _scatter()])) == "alpha"


def test_auto_overlay_without_common_backend_raises(registry):
    # Curve → {alpha, gamma}; Bars → {beta}; intersection empty (D4).
    with pytest.raises(errors.IncompatibleOverlayError):
        registry.auto_negotiate(qv.Overlay([_curve(), _bars()]))
