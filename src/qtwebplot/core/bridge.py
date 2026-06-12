"""The QObject exposed to JavaScript over QWebChannel.

This is intentionally tiny: one slot to receive an event, one slot for the
ready handshake, one slot to pipe console logs. Everything semantic happens
through the (name, payload) envelope.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot


class Bridge(QObject):
    """Python end of the JS<->Python bridge."""

    event = Signal(str, object)
    ready = Signal()
    log = Signal(str, str)

    @Slot(str, "QVariant")
    def emit_event(self, name: str, payload: Any) -> None:
        self.event.emit(name, payload)

    @Slot()
    def notify_ready(self) -> None:
        self.ready.emit()

    @Slot(str, str)
    def forward_log(self, level: str, message: str) -> None:
        self.log.emit(level, message)
