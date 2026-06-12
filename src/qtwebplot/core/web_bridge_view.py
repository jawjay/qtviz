"""WebBridgeView — the core widget. A QWebEngineView wrapper with a
bidirectional Python<->JS message bridge.

Knows nothing about plotting. Hosts arbitrary HTML+JS and routes named
messages in both directions.
"""

from __future__ import annotations

import json
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from qtwebplot.core._inject import inject_head_scripts, wrap_as_script
from qtwebplot.core._runtime import CORE_JS, load_qwebchannel_js
from qtwebplot.core.bridge import Bridge


# System message name used internally by JS to signal "no handler for this
# Python-sent message." Kept namespaced under `_qtwebplot.*` so it can't
# collide with a legitimate backend message.
_UNDELIVERED_NAME = "_qtwebplot.undelivered"

_CONSOLE_LEVEL_NAMES = {0: "info", 1: "warning", 2: "error"}


class _BridgePage(QWebEnginePage):
    """QWebEnginePage subclass that pipes JS console messages to the owning
    WebBridgeView's `log` signal."""

    def __init__(self, owner: "WebBridgeView", parent=None):
        super().__init__(parent)
        self._owner = owner

    def javaScriptConsoleMessage(  # noqa: N802 — Qt naming
        self, level, message: str, line: int, source: str
    ) -> None:
        level_str = _CONSOLE_LEVEL_NAMES.get(int(level), "info")
        location = f"{source}:{line}" if source else f"line {line}"
        self._owner.log.emit(level_str, f"{message} ({location})")


class _Throttle:
    """Trailing-edge throttle: emit immediately, then at most once every
    `ms` milliseconds, replaying the latest payload received during the
    cooldown window when it expires."""

    def __init__(self, view: "WebBridgeView", name: str, ms: int) -> None:
        self.view = view
        self.name = name
        self.ms = ms
        self.pending: Any = None
        self.has_pending = False
        self.timer = QTimer(view)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_tick)

    def submit(self, payload: Any) -> None:
        if not self.timer.isActive():
            self.view._emit_received(self.name, payload)
            self.timer.start(self.ms)
        else:
            self.pending = payload
            self.has_pending = True

    def _on_tick(self) -> None:
        if self.has_pending:
            payload = self.pending
            self.pending = None
            self.has_pending = False
            self.view._emit_received(self.name, payload)
            self.timer.start(self.ms)


def _default_debug_sink(direction: str, name: str, payload: Any, t: float) -> None:
    try:
        rendered = json.dumps(payload, default=str)
        if len(rendered) > 200:
            rendered = rendered[:197] + "..."
    except (TypeError, ValueError):
        rendered = repr(payload)
    print(
        f"[bridge {t:8.3f}] {direction:>4} {name:<28} {rendered}",
        file=sys.stderr,
    )


class WebBridgeView(QWidget):
    """Core widget — embeds a QWebEngineView with a bidirectional bridge.

    Signals
    -------
    ready : Signal()
        Emitted once the JS bridge has finished its handshake.
    received : Signal(str, object)
        Emitted on every JS->Python message: (name, payload).
    load_finished : Signal(bool)
        Forwarded from QWebEnginePage.loadFinished.
    log : Signal(str, str)
        JS console messages (info / warning / error) and any explicit logs.
    send_failed : Signal(str, object)
        Emitted when a Python->JS `send(name, payload)` could not be delivered
        (no JS handler registered for `name`). Useful for catching attach-order
        bugs and typos in handler names.
    """

    ready = Signal()
    received = Signal(str, object)
    load_finished = Signal(bool)
    log = Signal(str, str)
    send_failed = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._view = QWebEngineView(self)
        self._page = _BridgePage(self, self._view)
        self._view.setPage(self._page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._bridge = Bridge()
        self._channel = QWebChannel(self._page)
        self._channel.registerObject("bridge", self._bridge)
        self._page.setWebChannel(self._channel)

        self._is_ready = False
        self._command_queue: deque[tuple[str, Any]] = deque(maxlen=128)

        self._throttles: dict[str, _Throttle] = {}
        self._debug_sink: Callable[[str, str, Any, float], None] | None = None
        self._t0 = time.monotonic()

        self._bridge.event.connect(self._on_event)
        self._bridge.ready.connect(self._on_ready)
        self._bridge.log.connect(self.log)
        self._page.loadFinished.connect(self._on_load_finished)

    # ── content ──────────────────────────────────────────────────────────
    def load_html(self, html: str, *, base_url: QUrl | None = None) -> None:
        """Load an HTML document into the view, injecting the bridge bootstrap."""
        prepared = self._inject_runtime(html)
        self._is_ready = False
        self._view.setHtml(prepared, base_url or QUrl("about:blank"))

    def load_url(self, url: QUrl) -> None:
        """Load a URL. Note: external URLs must include the bridge bootstrap
        themselves; this is mainly useful for local resources."""
        self._is_ready = False
        self._view.setUrl(url)

    # ── messaging ────────────────────────────────────────────────────────
    def send(self, name: str, payload: Any = None) -> None:
        """Send a named message to JS. Queued if the bridge is not yet ready."""
        if self._debug_sink is not None:
            self._debug_sink("send", name, payload, time.monotonic() - self._t0)
        if not self._is_ready:
            if len(self._command_queue) == self._command_queue.maxlen:
                self._command_queue.popleft()
            self._command_queue.append((name, payload))
            return
        self._send_now(name, payload)

    # ── throttling ───────────────────────────────────────────────────────
    def set_throttle(self, name: str, ms: int) -> None:
        """Throttle the `received` signal for messages with this name to at
        most one emission per `ms` milliseconds (trailing-edge: the most
        recent payload during the cooldown window replays when it expires).

        Pass `ms <= 0` to remove throttling for this name.
        """
        existing = self._throttles.get(name)
        if ms <= 0:
            if existing is not None:
                existing.timer.stop()
                del self._throttles[name]
            return
        if existing is not None:
            existing.ms = ms
        else:
            self._throttles[name] = _Throttle(self, name, ms)

    def get_throttle(self, name: str) -> int:
        """Return the throttle in ms for `name`, or 0 if unthrottled."""
        t = self._throttles.get(name)
        return t.ms if t is not None else 0

    # ── debug ────────────────────────────────────────────────────────────
    def enable_debug_log(
        self,
        sink: Callable[[str, str, Any, float], None] | None = None,
    ) -> None:
        """Log every message crossing the bridge.

        `sink(direction, name, payload, elapsed_seconds)` is invoked for each
        message; `direction` is `"send"` (Py->JS) or `"recv"` (JS->Py). With
        no `sink`, a default prints to stderr with payload truncated at ~200
        characters.
        """
        self._debug_sink = sink or _default_debug_sink
        self._t0 = time.monotonic()

    def disable_debug_log(self) -> None:
        self._debug_sink = None

    # ── export ───────────────────────────────────────────────────────────
    def to_png(self, path: str | Path) -> Path:
        """Save the current view as a PNG.

        Synchronous — uses `QWebEngineView.grab()`, which captures whatever is
        currently rendered. The caller is responsible for waiting until the
        page has finished rendering.
        """
        pixmap = self._view.grab()
        out = Path(path)
        ok = pixmap.save(str(out), "PNG")
        if not ok:
            raise RuntimeError(f"Failed to save PNG to {out}")
        return out

    # ── escape hatches ───────────────────────────────────────────────────
    @property
    def web_view(self) -> QWebEngineView:
        return self._view

    @property
    def bridge(self) -> Bridge:
        return self._bridge

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def run_js(self, src: str, callback=None) -> None:
        """Pass-through to QWebEnginePage.runJavaScript."""
        if callback is None:
            self._page.runJavaScript(src)
        else:
            self._page.runJavaScript(src, callback)

    # ── injection ────────────────────────────────────────────────────────
    def _inject_runtime(self, html: str, extra_scripts: list[str] | None = None) -> str:
        scripts = [
            wrap_as_script(load_qwebchannel_js()),
            wrap_as_script(CORE_JS),
        ]
        if extra_scripts:
            scripts.extend(extra_scripts)
        return inject_head_scripts(html, scripts)

    # ── internals ────────────────────────────────────────────────────────
    def _send_now(self, name: str, payload: Any) -> None:
        encoded = json.dumps([name, payload], default=_json_default)
        self._page.runJavaScript(
            f"window.qtwebplot && window.qtwebplot._dispatch.apply(window.qtwebplot, {encoded});"
        )

    def _on_event(self, name: str, payload: object) -> None:
        # Intercept system messages.
        if name == _UNDELIVERED_NAME:
            if isinstance(payload, dict):
                self.send_failed.emit(
                    str(payload.get("name", "")),
                    payload.get("payload"),
                )
            return

        if self._debug_sink is not None:
            self._debug_sink("recv", name, payload, time.monotonic() - self._t0)

        throttle = self._throttles.get(name)
        if throttle is not None:
            throttle.submit(payload)
        else:
            self._emit_received(name, payload)

    def _emit_received(self, name: str, payload: Any) -> None:
        self.received.emit(name, payload)

    def _on_ready(self) -> None:
        self._is_ready = True
        while self._command_queue:
            name, payload = self._command_queue.popleft()
            self._send_now(name, payload)
        self.ready.emit()

    def _on_load_finished(self, ok: bool) -> None:
        self.load_finished.emit(ok)


def _json_default(obj: object) -> object:
    try:
        import numpy as np  # noqa: PLC0415

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
    except ImportError:
        pass
    if isinstance(obj, QObject):
        return None
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
