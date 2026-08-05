"""The example `__main__` path runs without a pre-existing QApplication.

The regression this pins (2026-08-04): `qv.show(build(), ...)` evaluated the
builder — constructing a View widget — *before* `show` could create the app;
Qt aborts on any QWidget built without one. [D141] closed it at the root:
`View.__init__` ensures a QApplication exists, so building a View app-less
can never crash the process (the builder-callable form of `show` remains as
a convenience).

Each case is a fresh subprocess (the only honest way to have no app);
`QApplication.exec` is patched to return immediately so nothing blocks.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytest.importorskip("qtviz")

_RUNNER = """
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
QApplication.exec = lambda *a, **k: 0   # don't block; the app must still be created
import runpy
runpy.run_path({path!r}, run_name="__main__")
print("MAIN-OK")
"""


@pytest.mark.tier2
@pytest.mark.parametrize("example", [
    "examples/01_hello.py",
    "examples/02_composition.py",
    "examples/31_axis_labels.py",
    "examples/35_everyday_figures.py",
    "examples/37_named_panes.py",
    "examples/38_inset_zoom.py",
])
def test_example_main_runs_without_a_preexisting_app(example):
    result = subprocess.run(
        [sys.executable, "-c", _RUNNER.format(path=example)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0 and "MAIN-OK" in result.stdout, (
        f"stdout={result.stdout!r}\nstderr={result.stderr[-1500:]}")


_VIEW_FIRST = """
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import qtviz as qv
# [D141]: constructing the View BEFORE any QApplication exists must not abort.
view = qv.View(qv.Scatter({"x": np.arange(3.0), "y": np.arange(3.0)}, x="x", y="y"))
from PySide6.QtWidgets import QApplication
QApplication.exec = lambda *a, **k: 0
qv.show(view, block=True)
print("VIEW-FIRST-OK")
"""


_IMPORT_IS_LAZY = """
import sys
import qtviz
heavy = [m for m in ("pyqtgraph", "matplotlib", "plotly", "bokeh")
         if m in sys.modules]
assert not heavy, f"import qtviz eagerly imported {heavy}"
print("LAZY-IMPORT-OK")
"""


@pytest.mark.tier2
def test_import_qtviz_does_not_load_backend_engines():
    """[D144]: backend entry points load on first registry use, not at import —
    `import qtviz` must not drag in pyqtgraph/matplotlib/plotly/bokeh."""
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_IS_LAZY],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0 and "LAZY-IMPORT-OK" in result.stdout, (
        f"stdout={result.stdout!r}\nstderr={result.stderr[-1500:]}")


@pytest.mark.tier2
def test_view_construction_without_app_cannot_abort():
    """[D141]: `qv.View(...)` in a bare script — the exact call that used to
    qFatal the process — creates the QApplication itself."""
    result = subprocess.run(
        [sys.executable, "-c", _VIEW_FIRST],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0 and "VIEW-FIRST-OK" in result.stdout, (
        f"stdout={result.stdout!r}\nstderr={result.stderr[-1500:]}")
