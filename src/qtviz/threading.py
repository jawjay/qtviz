"""Public threading surface (spec §2.14). Re-exports `qtviz.core.threading`."""

from __future__ import annotations

from .core.threading import (
    Worker,
    gui_thread,
    is_gui_thread,
    require_gui_thread,
    run_on_gui,
)

__all__ = ["require_gui_thread", "run_on_gui", "Worker", "is_gui_thread", "gui_thread"]
