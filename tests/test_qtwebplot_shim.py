"""The `qtwebplot` deprecation shim redirects to `qtviz.backends.webengine`.

Guards the backward-compat contract from the W0 rehome: old imports keep working,
resolve to the *same* module objects (no duplicate execution), and warn once.
"""

from __future__ import annotations

import os
import subprocess
import sys


def test_shim_redirects_top_level_and_submodules_to_same_objects() -> None:
    from qtwebplot.core._inject import inject_head_scripts

    import qtviz.backends.webengine as new_pkg
    import qtwebplot
    from qtviz.backends.webengine.core._inject import (
        inject_head_scripts as new_inject,
    )
    from qtwebplot import WebBridgeView

    # The old top-level name IS the new package object.
    assert qtwebplot is new_pkg
    assert WebBridgeView is new_pkg.WebBridgeView
    # Submodule imports through the old path resolve to the identical module.
    assert inject_head_scripts is new_inject
    # Legacy submodules that aren't re-exported at top level still import.
    from qtwebplot.layouts import PlotSplitter  # noqa: F401


def test_shim_warns_on_first_import() -> None:
    # The warning fires once per process at first import, so check it in a fresh
    # interpreter where `qtwebplot` hasn't been imported yet.
    code = "import warnings; warnings.simplefilter('always'); import qtwebplot"
    result = subprocess.run(
        [sys.executable, "-W", "always::DeprecationWarning", "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert result.returncode == 0, result.stderr
    assert "DeprecationWarning" in result.stderr
    assert "qtwebplot" in result.stderr
    assert "qtviz.backends.webengine" in result.stderr
