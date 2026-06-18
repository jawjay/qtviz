"""`View` — the user-facing widget (spec §2.9, milestone-data-core §4 / D13).

Owns an Element tree, a backend choice, a theme, the handle lifecycle, and the
canonical subscription registry (subscriptions survive a backend switch, Q-K).

Rendering is **async for lazy data**: if any bound ref is out-of-core, the
expensive `resolve_node` (materialize) runs on a worker thread; the View keeps
the last render visible (or a placeholder on first render), and a monotonic
build-id drops stale results when a newer build supersedes an in-flight one.
Eager data renders synchronously, exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..data import node_is_lazy, resolve_node
from ._host import render_root
from .disposable import Disposable
from .theme import Theme
from .threading import require_gui_thread


class _AsyncResolver(QObject):
    """Runs `resolve_node` on a thread pool (so a slow/blocked resolve doesn't
    stall others) and delivers each result back on the GUI thread via the
    `done` signal — emitted from a pool thread, so the cross-thread connection
    is queued onto the GUI event loop."""

    done = Signal(int, object, object)  # build_id, resolved_node | None, exception | None

    def __init__(self) -> None:
        super().__init__()
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qtviz-resolve")

    def submit(self, build_id: int, fn) -> None:
        self._pool.submit(self._run, build_id, fn)

    def _run(self, build_id: int, fn) -> None:
        try:
            self.done.emit(build_id, fn(), None)
        except Exception as e:  # noqa: BLE001
            self.done.emit(build_id, None, e)


_resolver: _AsyncResolver | None = None
_build_counter = 0


def _next_build_id() -> int:
    global _build_counter
    _build_counter += 1
    return _build_counter


def _shared_resolver() -> _AsyncResolver:
    global _resolver
    if _resolver is None:
        _resolver = _AsyncResolver()
    return _resolver


def _is_reactive(root) -> bool:
    """A reactive root is a Signal[Node] — duck-typed (get + subscribe) so core
    doesn't import the reactive package. Nodes (Element/Overlay/Layout) lack these."""
    return callable(getattr(root, "get", None)) and callable(getattr(root, "subscribe", None))


class View(QWidget):
    def __init__(self, root, *, backend="auto", theme: Theme | None = None, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme or Theme.light()
        self._backend_choice = backend
        self._subs: list[tuple] = []          # (event_type, cb, throttle_ms)
        self._handle = None
        self._superseded = None               # prior render kept visible during async rebuild
        self._placeholder: QLabel | None = None
        self._error: QLabel | None = None
        self._pending_state = None
        self._build_id = 0
        self._connected = False
        self._reactive_timer = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # Reactive root (spec §9 / D38): a Signal[Node] re-renders the View on change.
        if _is_reactive(root):
            self._root = root.get()
            sub = root.subscribe(self._on_root_signal)
            self.destroyed.connect(lambda: sub.dispose())  # no self-ref in the slot
        else:
            self._root = root
        self._build()

    def _backend_name(self) -> str:
        c = self._backend_choice
        return c if isinstance(c, str) else c.name

    # ── lifecycle ──
    @require_gui_thread
    def _build(self) -> None:
        self._build_id = _next_build_id()
        self._clear_error()
        if node_is_lazy(self._root):
            self._build_async(self._build_id)
        else:
            self._install(self._render(self._root))

    def _render(self, node):
        return render_root(node, view_backend=self._backend_name(), theme=self._theme)

    def _build_async(self, build_id: int) -> None:
        if self._handle is None and self._superseded is None:
            self._show_loading()  # first render — nothing to keep
        resolver = _shared_resolver()
        if not self._connected:
            resolver.done.connect(self._on_resolved)
            self._connected = True
        root = self._root
        resolver.submit(build_id, lambda: resolve_node(root))

    @Slot(int, object, object)
    def _on_resolved(self, build_id: int, resolved, exc) -> None:
        if build_id != self._build_id:
            return  # stale — a newer build superseded this one
        self._clear_loading()
        if exc is not None:
            self._drop_superseded()
            self._show_error(exc)
            return
        self._install(self._render(resolved))

    def _install(self, handle) -> None:
        self._drop_superseded()
        self._handle = handle
        self._layout.addWidget(handle.widget)
        for event_type, cb, ms in self._subs:
            handle.event_bus.subscribe(event_type, cb, throttle_ms=ms)
        if self._pending_state is not None:
            handle.restore_state(self._pending_state)
            self._pending_state = None

    def _drop_superseded(self) -> None:
        if self._superseded is not None:
            self._layout.removeWidget(self._superseded.widget)
            self._superseded.dispose()
            self._superseded = None

    @require_gui_thread
    def _rebuild(self) -> None:
        if self._handle is not None:  # keep current render visible until replacement is ready
            self._pending_state = self._handle.capture_state()
            self._superseded = self._handle
            self._handle = None
        self._build()

    def _on_root_signal(self, new_node) -> None:
        """Root `Signal[Node]` changed → re-render, debounced to one rebuild per Qt
        tick (D40); a `derived` may notify several times in a batch."""
        self._root = new_node
        if self._reactive_timer is None:
            self._reactive_timer = QTimer(self)
            self._reactive_timer.setSingleShot(True)
            self._reactive_timer.timeout.connect(self._rebuild)
        self._reactive_timer.start(0)

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

    # ── placeholder / error ──
    def _show_loading(self) -> None:
        if self._placeholder is None:
            self._placeholder = QLabel("Loading…")
            self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._placeholder)

    def _clear_loading(self) -> None:
        if self._placeholder is not None:
            self._layout.removeWidget(self._placeholder)
            self._placeholder.setParent(None)
            self._placeholder = None

    def _show_error(self, exc: BaseException) -> None:
        self._error = QLabel(f"data error: {exc}")
        self._layout.addWidget(self._error)

    def _clear_error(self) -> None:
        if self._error is not None:
            self._layout.removeWidget(self._error)
            self._error.setParent(None)
            self._error = None

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

    def native(self, element_id: str):
        """The live backend primitive for an element (`handle.native`, [D53]) — the
        escape valve for backend-native work (ROIs, crosshairs, native signals) the
        typed events don't expose. `None` if not rendered. Non-portable by design."""
        return self._handle.native(element_id) if self._handle is not None else None

    @property
    def loading(self) -> bool:
        return self._placeholder is not None or self._superseded is not None
