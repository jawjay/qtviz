"""GUI-thread discipline (spec §2.14).

All Qt construction/mutation happens on the GUI thread. Public entry points
(Backend.render, RenderHandle mutators, View.set_*) are guarded with
`@require_gui_thread` (D5: guard entries, trust the renderers beneath them).
Data prep / queries run on workers and marshal results back via `run_on_gui`.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from functools import wraps
from typing import TypeVar

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

T = TypeVar("T")


def gui_thread() -> QThread | None:
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    app = QApplication.instance()
    return app.thread() if app is not None else None


def is_gui_thread() -> bool:
    t = gui_thread()
    if t is None:
        return True  # no QApplication yet → permissive
    return QThread.currentThread() == t


def require_gui_thread(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_gui_thread():
            raise RuntimeError(
                f"{getattr(fn, '__qualname__', fn)} must be called on the GUI thread"
            )
        return fn(*args, **kwargs)

    return wrapper


class _GuiInvoker(QObject):
    """Marshals a callable onto the GUI thread via a queued signal."""

    _trigger = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        thread = gui_thread()
        if thread is not None:
            self.moveToThread(thread)
        self._trigger.connect(self._run, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _run(self, job) -> None:
        fn, fut = job
        try:
            fut.set_result(fn())
        except Exception as e:  # noqa: BLE001
            fut.set_exception(e)


_invoker: _GuiInvoker | None = None


def run_on_gui(fn: Callable[[], T], *, block: bool = False) -> Future:
    """Schedule `fn` on the GUI thread. Called *from* the GUI thread it
    short-circuits and runs `fn` directly (no deadlock; Q-E)."""
    fut: Future = Future()
    if is_gui_thread():
        try:
            fut.set_result(fn())
        except Exception as e:  # noqa: BLE001
            fut.set_exception(e)
        return fut

    global _invoker
    if _invoker is None:
        _invoker = _GuiInvoker()
    _invoker._trigger.emit((fn, fut))
    if block:
        fut.result()
    return fut


class Worker(QObject):
    """Public convenience — a QObject living on its own QThread that runs
    submitted callables and resolves their Futures. For DataSource
    implementers, plugin authors, Studio (spec §2.14)."""

    _submit = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._submit.connect(self._run, Qt.ConnectionType.QueuedConnection)
        self._thread.start()

    @Slot(object)
    def _run(self, job) -> None:
        fn, fut = job
        try:
            fut.set_result(fn())
        except Exception as e:  # noqa: BLE001
            fut.set_exception(e)

    def submit(self, fn: Callable[[], T]) -> Future:
        fut: Future = Future()
        self._submit.emit((fn, fut))
        return fut

    def stop(self) -> None:
        self._thread.quit()
        self._thread.wait()
