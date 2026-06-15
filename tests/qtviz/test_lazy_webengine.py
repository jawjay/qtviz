"""WebEngine (Chromium) must not load at `import qtviz`.

The webengine backend registers (name / capabilities / supports) without importing
the QtWebEngine widgets — those load only when a webengine view is actually
rendered. This keeps the default suite Chromium-free: faster, and free of the
offscreen Chromium init/teardown segfault that only bites once WebEngine is loaded.
Checked in a fresh interpreter so prior test imports can't mask a regression.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

pytestmark = pytest.mark.tier1

_PROBE = (
    "import sys, qtviz, qtviz.backends as B\n"
    "assert 'webengine' in B.list_available(), 'webengine not registered'\n"
    "assert B.get('webengine').supports(qtviz.RawFigure), 'RawFigure support lost'\n"
    "we = [m for m in sys.modules if 'WebEngine' in m]\n"
    "assert not we, 'import qtviz loaded QtWebEngine: ' + repr(we)\n"
    "print('OK')\n"
)


def test_import_qtviz_does_not_load_webengine():
    result = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True)
    assert result.returncode == 0 and "OK" in result.stdout, (
        f"stdout={result.stdout!r}\nstderr={result.stderr[-1500:]}"
    )
