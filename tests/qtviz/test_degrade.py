"""Tier-1 — the honor-or-warn mechanism (spec §3.4, [D51]).

Pure: exercises `core/_degrade.check_recommended` directly, no Qt / no backend.
"""

from __future__ import annotations

import warnings

import pytest

qv = pytest.importorskip("qtviz")

from qtviz.core import _degrade  # noqa: E402
from qtviz.errors import QtvizWarning  # noqa: E402

pytestmark = pytest.mark.tier1


def _scatter(**kw):
    return qv.Scatter({"x": [0.0, 1.0, 2.0], "y": [0.0, 1.0, 2.0]}, x="x", y="y", **kw)


def _qtviz_warnings(caught):
    return [w for w in caught if issubclass(w.category, QtvizWarning)]


def test_default_valued_recommended_option_is_silent():
    """A recommended option left at its constructor default never warns — so a
    plain `Scatter()` is quiet even on a backend that honors nothing."""
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _degrade.check_recommended(_scatter(), backend_name="b", honored=frozenset())
    assert not _qtviz_warnings(caught)


def test_unhonored_nondefault_warns_exactly_once():
    """A non-default recommended option a backend doesn't honor warns — and only
    once per (backend, element_type, option), not once per render."""
    _degrade.reset()
    el = _scatter(marker="square")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(3):
            _degrade.check_recommended(el, backend_name="pyqtgraph", honored=frozenset())
    warned = _qtviz_warnings(caught)
    assert len(warned) == 1
    assert "'marker'" in str(warned[0].message)


def test_honored_option_never_warns():
    _degrade.reset()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _degrade.check_recommended(
            _scatter(marker="square"), backend_name="b", honored=frozenset({"marker"})
        )
    assert not _qtviz_warnings(caught)


def test_reset_rearms_the_warning():
    """`reset()` clears the once-registry so the warning can fire again (tests)."""
    el = _scatter(marker="square")
    for _ in range(2):
        _degrade.reset()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _degrade.check_recommended(el, backend_name="pyqtgraph", honored=frozenset())
        assert len(_qtviz_warnings(caught)) == 1


def test_distinct_backends_warn_independently():
    _degrade.reset()
    el = _scatter(alpha=0.5)  # honored on matplotlib, not on pyqtgraph
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _degrade.check_recommended(el, backend_name="pyqtgraph", honored=frozenset())
        _degrade.check_recommended(el, backend_name="matplotlib", honored=frozenset({"alpha"}))
    warned = _qtviz_warnings(caught)
    assert len(warned) == 1 and "pyqtgraph" in str(warned[0].message)


