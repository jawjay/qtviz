"""The example `__main__` path runs without a pre-existing QApplication.

The regression this pins (2026-08-04): `qv.show(build(), ...)` evaluated the
builder — constructing a View widget — *before* `show` could create the app;
Qt aborts on any QWidget built without one. Examples now pass the builder
itself (`qv.show(build, ...)`), which `show` invokes after the app exists.

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
])
def test_example_main_runs_without_a_preexisting_app(example):
    result = subprocess.run(
        [sys.executable, "-c", _RUNNER.format(path=example)],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0 and "MAIN-OK" in result.stdout, (
        f"stdout={result.stdout!r}\nstderr={result.stderr[-1500:]}")
