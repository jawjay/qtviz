"""Tier-3 — backend conformance (spec §2.4–§2.8, dev-plan §5.3).

One parametrized suite every backend must pass. Adding a backend = make this
green. Parametrized over `list_available()`, so it covers zero backends today
and each real backend the moment it registers. The decisive test is
`test_adding_backend_touches_only_its_dir` — enforced socially, asserted here
structurally: a backend is exercised purely through the `Backend` protocol.
"""

from __future__ import annotations

import pytest

qv = pytest.importorskip("qtviz")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

pytestmark = [pytest.mark.tier2, pytest.mark.conformance]

_KNOWN_EXPORTS = {"png", "svg", "pdf", "html"}
_PICKING = {"native", "approximate", "none"}


def _supported(backend, make_elements):
    return [el for el in make_elements(qv).values() if backend.supports(type(el))]


def test_capabilities_internally_consistent(backend):
    caps = backend.capabilities
    assert set(caps.dimensions) <= {2, 3} and caps.dimensions
    assert caps.picking in _PICKING
    assert caps.brush in _PICKING
    assert set(caps.exports) <= _KNOWN_EXPORTS
    assert caps.max_recommended_points > 0


def test_supports_matches_registered_renderers(backend):
    for element_type in backend.renderers.types():
        assert backend.supports(element_type)


def test_renders_and_disposes_each_supported_element(backend, make_elements, qtbot):
    supported = _supported(backend, make_elements)
    assert supported, f"{backend.name} declares no supported elements"
    for el in supported:
        handle = backend.render(el, theme=qv.Theme.light())
        assert isinstance(handle.widget, QtWidgets.QWidget)
        assert handle.backend_name == backend.name
        qtbot.addWidget(handle.widget)
        handle.dispose()  # must not raise


def test_state_round_trips(backend, make_elements, qtbot):
    el = _supported(backend, make_elements)[0]
    handle = backend.render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    handle.restore_state(handle.capture_state())  # capture→restore, no raise [D2]


def test_each_declared_export_writes_a_file(backend, make_elements, qtbot, tmp_path):
    el = _supported(backend, make_elements)[0]
    handle = backend.render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    for fmt in backend.capabilities.exports:
        out = handle.export(fmt, tmp_path / f"plot.{fmt}")
        assert out.exists() and out.stat().st_size > 0


def test_subscription_returns_a_disposable(backend, make_elements, qtbot):
    el = _supported(backend, make_elements)[0]
    handle = backend.render(el, theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    disposable = handle.event_bus.subscribe(qv.PickEvent, lambda ev: None)
    disposable.dispose()  # idempotent cleanup, no raise
