"""Tier-3 — backend conformance (spec §2.4–§2.8, dev-plan §5.3).

One parametrized suite every backend must pass. Adding a backend = make this
green. Parametrized over `list_available()`, so it covers zero backends today
and each real backend the moment it registers. The decisive test is
`test_adding_backend_touches_only_its_dir` — enforced socially, asserted here
structurally: a backend is exercised purely through the `Backend` protocol.
"""

from __future__ import annotations

import warnings

import pytest

qv = pytest.importorskip("qtviz")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from qtviz.core import _degrade  # noqa: E402
from qtviz.errors import QtvizWarning  # noqa: E402

pytestmark = [pytest.mark.tier2, pytest.mark.conformance]

_KNOWN_EXPORTS = {"png", "svg", "pdf", "html"}
_PICKING = {"native", "approximate", "none"}

# A valid non-default value per *scalar* recommended option. Column-valued options
# (color_by / size_by) need a real column and are honored on every backend, so
# they're covered by the render tests rather than this warn/honor matrix.
_NON_DEFAULT = {
    "marker": "square", "alpha": 0.5, "line_style": "dashed", "line_width": 3.0,
    "step": "post", "hole": 0.4, "axis": "y2", "levels": 4, "filled": True,
    "head": "both", "fill": True, "rotation": 30.0, "valign": "top", "frame": True,
    "annotate": ".1f", "marker_every": 3,
    "norm": "power", "clim": (0.2, 0.9),  # (gamma/linthresh/levels live inside Norm, [D130])
    "arrow_scale": 0.5, "head_scale": 2.0, "baseline": 0.5,
    # ("mode" is skipped: stacking requires by=)
    "interpolation": "nearest", "colormap": "plasma", "aggregator": "sum",
    "by": "cat", "orient": "horizontal", "direction": "x", "bins": 7, "density": True,
    "color": "#ff0000", "size": 10.0, "label": "series-A", "halign": "left",
}


def _supported(backend, make_elements):
    return [el for el in make_elements(qv).values() if backend.supports(type(el))]


def test_capabilities_internally_consistent(backend):
    caps = backend.capabilities
    assert set(caps.dimensions) <= {2, 3} and caps.dimensions
    assert caps.picking in _PICKING
    assert caps.brush in _PICKING
    assert set(caps.exports) <= _KNOWN_EXPORTS
    assert caps.max_recommended_points > 0


def test_no_aspirational_capabilities(backend):
    """Capability honesty ([D52]): a backend must not declare a capability with no
    code path behind it. No backend renders 3-D or animates yet, so neither may be
    claimed — update this assertion together with the implementing renderer when one
    lands. (0.1 shipped `dimensions={2,3}`/`animation=True` aspirationally.)"""
    caps = backend.capabilities
    assert 3 not in caps.dimensions, f"{backend.name} claims 3-D with no 3-D renderer"
    assert caps.animation is False, f"{backend.name} claims animation with no animation API"


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


def test_recommended_options_are_honored_or_warned(backend, make_elements, qtbot):
    """Anti-silent-drop guard (R4 / [D51]): for every supported element, each
    recommended option set to a non-default value is either *honored* (no warning)
    or *warn-and-degrades* (exactly one QtvizWarning) — never silently dropped.

    This is the test that makes "never silent" enforced by the suite rather than by
    convention: a renderer that stops honoring a declared-honored option, or that
    silently drops a new one, fails here. Every backend also declares
    `honored_options(element_type)` — part of the §3.4 contract."""
    for el in _supported(backend, make_elements):
        et = type(el)
        honored = backend.honored_options(et)
        for opt in et.RECOMMENDED_OPTIONS:
            if opt not in _NON_DEFAULT:
                continue  # column-valued (color_by/size_by) — honored everywhere
            if opt in ("norm", "clim") and et.__name__ == "Scatter":
                # Scatter norm/clim ride the color_by mapping and require
                # color_by (absent from the base fixture) — their honor path
                # is covered by test_color_norm
                continue
            variant = el.with_(**{opt: _NON_DEFAULT[opt]})
            _degrade.reset()  # re-arm the warn-once registry for this assertion
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                handle = backend.render(variant, theme=qv.Theme.light())
                qtbot.addWidget(handle.widget)
                handle.dispose()
            warned = [
                w for w in caught
                if issubclass(w.category, QtvizWarning) and f"'{opt}'" in str(w.message)
            ]
            if opt in honored:
                assert not warned, (
                    f"{backend.name}/{et.__name__}: honored '{opt}' must not warn"
                )
            else:
                assert len(warned) == 1, (
                    f"{backend.name}/{et.__name__}: dropped '{opt}' must warn once "
                    f"(got {len(warned)}) — silent drops are forbidden (§3.4/[D51])"
                )
