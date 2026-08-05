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


def _is_live_ref(ref) -> bool:
    """A live data ref (a `qv.stream`, or any third-party ref speaking the same
    dialect): subscribable AND versioned — the marker that its contents change
    underneath a render ([D76])."""
    return callable(getattr(ref, "subscribe", None)) and callable(getattr(ref, "version", None))


class _StreamBinding:
    """Live-data glue ([D77], resolves [D7]): one subscription per distinct live
    ref in the *original* (unresolved) root — the resolved tree holds snapshots.
    Appends arrive on any thread; the View's queued `_stream_notified` signal
    marshals to the GUI thread, where the View's single-shot 0 ms timer
    coalesces a burst into **one refresh per event-loop tick**. Deliberately
    NOT a QObject: bindings churn at every rebuild, and queued/timer delivery
    to a just-disposed QObject mis-resolves its slot ("Slot not found") — all
    Qt plumbing lives on the View, which never churns. A refresh re-resolves
    the live elements and writes them in place (`handle.set_element_data`); if
    any element can't take the fast path, it degrades explicitly —
    `handle.update` (webengine's Plotly-react diff) or a full View rebuild
    (matplotlib)."""

    def __init__(self, view: View, root) -> None:
        from .compose import _elements_of  # noqa: PLC0415

        self._view = view
        self._elements = [el for el in _elements_of(root)
                          if _is_live_ref(getattr(el, "data", None))]
        refs = {id(el.data): el.data for el in self._elements}
        self._disposed = False
        self._subs = [ref.subscribe(self._on_append) for ref in refs.values()]

    @property
    def live(self) -> bool:
        return bool(self._elements)

    def _on_append(self, _ref) -> None:
        import contextlib  # noqa: PLC0415

        # any thread → queued onto the GUI event loop via the *View's* signal;
        # the View outlives every binding, so a queued event can't land on a
        # churned receiver. A disposal can still race an in-flight append, and
        # emitting on a dead QObject is fatal — hence the suppress.
        with contextlib.suppress(RuntimeError):
            self._view._stream_notified.emit()

    def _refresh(self) -> None:
        handle = self._view.handle
        if handle is None:
            return  # mid-rebuild; the new render reads the fresh buffer anyway
        ok = True
        for el in self._elements:
            arrays = el.data.resolve_channels(el.channels(), who=type(el).__name__)
            if not handle.set_element_data(el.id, arrays):
                ok = False
                break
        if ok:
            return
        try:
            from ..data import resolve_node  # noqa: PLC0415

            handle.update(resolve_node(self._view._root))
        except NotImplementedError:
            self._view._rebuild()  # the honest slow path (mpl: streaming=False)

    def dispose(self) -> None:
        self._disposed = True  # a queued notification may still land — ignore it
        for sub in self._subs:
            sub.dispose()
        self._subs = []


class View(QWidget):
    # Cross-thread marshal for live-data appends ([D77]): emitted (queued) from
    # any thread, delivered here — the stable receiver — then routed to the
    # *current* binding. Bindings are rebuilt at every install; queued events
    # addressed to a disposed one mis-resolve ("Slot not found"), the View never
    # churns.
    _stream_notified = Signal()

    def __init__(self, root, *, backend="auto", theme: Theme | None = None,
                 toolbar: bool = False, parent=None) -> None:
        super().__init__(parent)
        from .theme import default_theme  # noqa: PLC0415

        self._theme = theme or default_theme()
        self._backend_choice = backend
        self._subs: list[tuple] = []          # (event_type, cb, throttle_ms)
        self._want_toolbar = toolbar          # backend-native toolbar ([D95])
        self._toolbar_widget = None
        self._handle = None
        self._binding: _StreamBinding | None = None  # live-data glue ([D77])
        self._superseded = None               # prior render kept visible during async rebuild
        self._placeholder: QLabel | None = None
        self._error: QLabel | None = None
        self._pending_state = None
        self._build_id = 0
        self._connected = False
        self._reactive_timer: QTimer | None = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._stream_notified.connect(self._on_stream_notified)
        self._stream_timer = QTimer(self)  # coalesces appends: one refresh/tick
        self._stream_timer.setSingleShot(True)
        self._stream_timer.timeout.connect(self._on_stream_tick)
        # Lifecycle hygiene: dispose the active handle (event-bus throttles,
        # raster controllers, selector hooks) when the View is destroyed —
        # replaced handles are already disposed at swap; the LAST one wasn't,
        # leaving parentless QTimers behind widget deletion (teardown races).
        box = self._handle_box = [None]

        def _release_last(*_a, _box=box) -> None:
            handle = _box[0]
            _box[0] = None
            if handle is not None:
                handle.release()  # Qt owns the widget teardown at this point

        self.destroyed.connect(_release_last)
        # Reactive root (spec §9 / D38): a Signal[Node] re-renders the View on change.
        if _is_reactive(root):
            self._root = root.get()
            sub = root.subscribe(self._on_root_signal)
            self.destroyed.connect(lambda: sub.dispose())  # no self-ref in the slot
        else:
            self._root = root
        self._build()

    @Slot()
    def _on_stream_notified(self) -> None:
        if self._binding is not None and not self._binding._disposed:
            self._stream_timer.start(0)  # coalesce ([D7]/[D40])

    @Slot()
    def _on_stream_tick(self) -> None:
        b = self._binding
        if b is not None and not b._disposed:
            b._refresh()

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
        self._handle_box[0] = handle
        if self._toolbar_widget is not None:  # belongs to the outgoing canvas
            self._layout.removeWidget(self._toolbar_widget)
            self._toolbar_widget.setParent(None)
            self._toolbar_widget.deleteLater()
            self._toolbar_widget = None
        self._drop_superseded()
        self._handle = handle
        if self._want_toolbar:
            tb = handle.toolbar()
            if tb is not None:
                self._layout.addWidget(tb)
                self._toolbar_widget = tb
        self._layout.addWidget(handle.widget)
        for event_type, cb, ms in self._subs:
            handle.event_bus.subscribe(event_type, cb, throttle_ms=ms)
        if self._pending_state is not None:
            handle.restore_state(self._pending_state)
            self._pending_state = None
        if self._binding is not None:
            self._binding.dispose()
            self._binding = None
        binding = _StreamBinding(self, self._root)
        if binding.live:
            self._binding = binding
            self.destroyed.connect(binding.dispose)

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
    def on(self, event_type: type, cb: Callable, *, throttle_ms: int | None = None,
           source=None) -> Disposable:
        """Subscribe to a typed event. `source=` ([D134]) filters by the
        emitting element — pass an Element (or its id), or a sequence of
        either; it replaces the `e.source_id == el.id` lambda idiom."""
        if source is not None:
            items = source if isinstance(source, (list, tuple, set)) else (source,)
            wanted = frozenset(getattr(x, "id", x) for x in items)
            inner = cb

            def cb(ev, _inner=inner, _wanted=wanted):  # noqa: A001 — deliberate rebind
                if getattr(ev, "source_id", None) in _wanted:
                    _inner(ev)
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


def show(root, *, title: str | None = None, size: tuple[int, int] = (960, 640),
         backend: str = "auto", theme: Theme | None = None, block: bool = True) -> View:
    """[D134] the one-liner for scripts: wrap `root` in a `View` (an existing
    `View` passes through), size/title/show it, and — with `block=True` — run
    the Qt event loop. Returns the View either way, so `block=False` hands
    back a live widget for embedding or tests. `View` itself stays a plain
    QWidget for real applications.

    `root` may also be a **zero-argument callable** returning the node or a
    ready `View` — it runs *after* the QApplication exists. Pass the builder
    when it constructs widgets (`qv.show(build)`, not `qv.show(build())`):
    Python evaluates arguments before `show` can create the app, and Qt
    aborts on any QWidget built without one. Elements are Qt-free, so
    `qv.show(qv.Scatter(...))` is always safe."""
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    app = QApplication.instance() or QApplication([])
    if callable(root) and not isinstance(root, View):
        root = root()  # deferred builder — widgets are safe now
    view = root if isinstance(root, View) else View(root, backend=backend, theme=theme)
    view.resize(*size)
    if title is not None:
        view.setWindowTitle(title)
    view.show()
    if block:
        app.exec()
    return view
