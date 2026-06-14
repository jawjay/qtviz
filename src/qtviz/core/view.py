"""`View` — the user-facing widget (spec §2.9).

Owns an Element tree, a backend choice, a theme, and the handle lifecycle.
Holds the canonical subscription registry so subscriptions survive a backend
switch (Q-K). The only class users routinely instantiate.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ._host import render_root
from .disposable import Disposable
from .theme import Theme
from .threading import require_gui_thread


class View(QWidget):
    def __init__(self, root, *, backend="auto", theme: Theme | None = None, parent=None) -> None:
        super().__init__(parent)
        self._root = root
        self._theme = theme or Theme.light()
        self._backend_choice = backend
        self._subs: list[tuple] = []          # (event_type, cb, throttle_ms)
        self._handle = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._build()

    # ── lifecycle ──
    @require_gui_thread
    def _build(self) -> None:
        choice = self._backend_choice
        name = choice if isinstance(choice, str) else choice.name
        self._handle = render_root(self._root, view_backend=name, theme=self._theme)
        self._layout.addWidget(self._handle.widget)
        for event_type, cb, ms in self._subs:
            self._handle.event_bus.subscribe(event_type, cb, throttle_ms=ms)

    @require_gui_thread
    def _rebuild(self) -> None:
        old = self._handle
        state = old.capture_state() if old is not None else None
        if old is not None:
            self._layout.removeWidget(old.widget)
            old.dispose()
            self._handle = None
        self._build()
        if state is not None:
            self._handle.restore_state(state)

    @require_gui_thread
    def set_backend(self, name_or_backend) -> None:
        self._backend_choice = name_or_backend
        self._rebuild()

    @require_gui_thread
    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._rebuild()

    @require_gui_thread
    def set_root(self, root) -> None:
        self._root = root
        self._rebuild()

    # ── events ──
    def on(self, event_type: type, cb: Callable, *, throttle_ms: int | None = None) -> Disposable:
        record = (event_type, cb, throttle_ms)
        self._subs.append(record)
        live = (
            self._handle.event_bus.subscribe(event_type, cb, throttle_ms=throttle_ms)
            if self._handle is not None
            else None
        )

        def teardown() -> None:
            if record in self._subs:
                self._subs.remove(record)
            if live is not None:
                live.dispose()

        return Disposable(teardown)

    @property
    def handle(self):
        return self._handle
