"""S-style reactivity — Signal / derived / effect / batch (spec §9; D38–D40).

Auto-tracking: while a `derived`/`effect` body runs, it sits on the `_observers`
stack and every `Signal.get()` registers it as a subscriber — so dependencies are
discovered automatically. Synchronous, GUI-thread-only (a cross-thread `set`
marshals via `run_on_gui`); simple propagation + `batch()` to coalesce, *not*
topological/glitch-free (D39). The whole graph is tiny and runs on one thread, so
no locks.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from ..core.disposable import Disposable
from ..core.threading import is_gui_thread, run_on_gui

T = TypeVar("T")

# A computation currently running (effect or derived) auto-tracks its reads.
_observers: list[_Computation] = []
# Batching: while depth > 0, notifications are deferred and de-duplicated.
_batch_depth = 0
_pending: dict[Any, None] = {}


def _current_observer() -> _Computation | None:
    return _observers[-1] if _observers else None


def _notify(subs) -> None:
    """Deliver change notifications now, or defer to the end of a `batch`."""
    if _batch_depth > 0:
        for s in subs:
            _pending[s] = None
    else:
        for s in list(subs):  # snapshot — the set mutates as deps re-track
            s._notify()


class Signal(Generic[T]):
    """A reactive cell: read with `get()` (auto-tracks), write with `set()`."""

    def __init__(self, value: T) -> None:
        self._value = value
        self._subs: set = set()  # _Computation | _CallbackSub

    def get(self) -> T:
        obs = _current_observer()
        if obs is not None:
            obs._track(self)
        return self._value

    def set(self, value: T) -> None:
        if not is_gui_thread():
            run_on_gui(lambda: self.set(value))  # marshal onto the GUI thread (D40)
            return
        self._value = value
        _notify(self._subs)

    def subscribe(self, cb: Callable[[T], None]) -> Disposable:
        sub = _CallbackSub(self, cb)
        self._subs.add(sub)
        return Disposable(lambda: self._subs.discard(sub))


class _CallbackSub:
    """A plain `Signal.subscribe(cb)` — `cb(value)` on change (not auto-tracked)."""

    __slots__ = ("_signal", "_cb")

    def __init__(self, signal: Signal, cb: Callable[[Any], None]) -> None:
        self._signal = signal
        self._cb = cb

    def _notify(self) -> None:
        self._cb(self._signal._value)


class _Tracking:
    """Mixin: the dependency-tracking half of a computation."""

    _deps: set

    def _track(self, signal: Signal) -> None:
        self._deps.add(signal)
        signal._subs.add(self)

    def _clear_deps(self) -> None:
        for s in self._deps:
            s._subs.discard(self)
        self._deps.clear()

    def _run_tracked(self, fn: Callable[[], Any]) -> Any:
        self._clear_deps()
        _observers.append(self)
        try:
            return fn()
        finally:
            _observers.pop()


class _Computation(_Tracking):
    """An `effect`: re-runs its body whenever a tracked dependency changes."""

    def __init__(self, fn: Callable[[], None]) -> None:
        self._fn = fn
        self._deps = set()
        self._disposed = False
        self._run()

    def _run(self) -> None:
        if not self._disposed:
            self._run_tracked(self._fn)

    def _notify(self) -> None:
        self._run()

    def dispose(self) -> None:
        self._disposed = True
        self._clear_deps()


class _Derived(Signal[T], _Tracking):
    """A computed `Signal`: recomputes when a tracked dependency changes; memoized."""

    def __init__(self, fn: Callable[[], T]) -> None:
        super().__init__(None)  # type: ignore[arg-type]
        self._fn = fn
        self._deps = set()
        self._stale = True

    def _recompute(self) -> None:
        self._value = self._run_tracked(self._fn)
        self._stale = False

    def get(self) -> T:
        if self._stale:
            self._recompute()
        obs = _current_observer()
        if obs is not None:
            obs._track(self)  # downstream observers depend on this derived
        return self._value

    def _notify(self) -> None:
        self._recompute()
        _notify(self._subs)

    def set(self, value: T) -> None:
        raise AttributeError("a derived signal is read-only")


# ── public API ────────────────────────────────────────────────────────────────
def signal(initial: T) -> Signal[T]:
    return Signal(initial)


def derived(fn: Callable[[], T]) -> Signal[T]:
    return _Derived(fn)


def effect(fn: Callable[[], None], *, owner=None) -> Disposable:
    comp = _Computation(fn)
    disp = Disposable(comp.dispose)
    if owner is not None:
        owner.destroyed.connect(disp.dispose)  # auto-dispose with a QObject (D40)
    return disp


def batch(fn: Callable[[], None]) -> None:
    """Run `fn`, coalescing all `set`s into a single notification pass."""
    global _batch_depth
    _batch_depth += 1
    try:
        fn()
    finally:
        _batch_depth -= 1
        if _batch_depth == 0 and _pending:
            subs = list(_pending)
            _pending.clear()
            for s in subs:
                s._notify()
