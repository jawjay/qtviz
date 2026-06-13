"""`Disposable` — the uniform teardown handle returned by every subscription.

`DataRef.subscribe`, `EventBus.subscribe`, `effect()`, … all return one of
these. `dispose()` is idempotent; disposing twice is a no-op.
"""

from __future__ import annotations

from collections.abc import Callable


class Disposable:
    """Wraps a teardown callable. Idempotent."""

    __slots__ = ("_teardown", "_disposed")

    def __init__(self, teardown: Callable[[], None] | None = None) -> None:
        self._teardown = teardown
        self._disposed = False

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._teardown is not None:
            self._teardown()

    @property
    def disposed(self) -> bool:
        return self._disposed


NOOP = Disposable()  # shared no-op for static refs
