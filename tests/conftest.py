"""Session-wide test configuration.

Run Qt headless by default — set the platform before any Qt import so widget /
WebEngine tests don't require a display. Override by exporting
``QT_QPA_PLATFORM`` yourself.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
