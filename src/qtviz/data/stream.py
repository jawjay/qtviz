"""The streaming data source ([D76], milestone-0.6-live §1).

`StreamRef` is a mutable, append-able tabular `DataRef` with a ring-buffer
rolling window. It notifies through the base contract's `subscribe` seam —
designed in Phase 1, stubbed NOOP everywhere until now. Pure Python + numpy,
no Qt: `append` is thread-safe under a lock; whoever subscribes owns the
GUI-thread marshaling (the View's `StreamBinding`, increment 2).

Purity (R1/[D38]): the Element holding a StreamRef stays immutable — it holds
a handle to changing data, exactly like a pandas frame the user mutates. The
only new power is that this handle *tells* its subscribers.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import numpy as np

from ..core.disposable import Disposable
from ..errors import ValidationError
from .ref import Schema, TabularRef

_GROW = 1024  # initial capacity; doubles amortized


class StreamRef(TabularRef):
    """Append-able named columns with an optional rolling `window` (max rows —
    old rows drop as new ones arrive, the spec §12 "stream-time auto-rolling"
    deferral lifted). `is_lazy` stays False: reads are cheap in-memory slices;
    nothing here needs the async resolve path."""

    is_lazy = False

    def __init__(self, columns: dict[str, Any], *, window: int | None = None) -> None:
        if not columns:
            raise ValidationError("stream needs at least one column: {'name': dtype}")
        if window is not None and int(window) < 1:
            raise ValidationError(f"window must be a positive row count, got {window}")
        self._dtypes = {str(n): np.dtype(dt) for n, dt in columns.items()}
        self._window = int(window) if window is not None else None
        self._lock = threading.Lock()
        self._cap = _GROW if self._window is None else min(_GROW, self._window)
        self._buf = {n: np.empty(self._cap, dtype=dt) for n, dt in self._dtypes.items()}
        self._len = 0
        self._version = 0
        self._subs: list[Callable] = []

    # ── producer side (any thread) ──
    def append(self, **columns: Any) -> None:
        """Append rows (scalars or equal-length 1-D arrays for every column).
        Thread-safe; fires each subscriber once per append (after the write)."""
        missing = set(self._dtypes) - set(columns)
        extra = set(columns) - set(self._dtypes)
        if missing or extra:
            raise ValidationError(
                f"append needs exactly the stream's column(s) {sorted(self._dtypes)}; "
                f"missing {sorted(missing)}, unexpected {sorted(extra)}"
            )
        arrays = {n: np.atleast_1d(np.asarray(v, dtype=self._dtypes[n]))
                  for n, v in columns.items()}
        lengths = {len(a) for a in arrays.values()}
        if len(lengths) != 1:
            raise ValidationError(
                f"append columns have mismatched lengths: "
                f"{ {n: len(a) for n, a in arrays.items()} }"
            )
        n_new = lengths.pop()
        with self._lock:
            self._write(arrays, n_new)
            self._version += 1
        for cb in list(self._subs):
            cb(self)

    def _write(self, arrays: dict[str, np.ndarray], n_new: int) -> None:
        w = self._window
        if w is not None and n_new >= w:
            # one append larger than the window: keep only its tail
            for name in self._buf:
                self._buf[name] = arrays[name][-w:].copy()
            self._cap, self._len = w, w
            return
        drop = 0
        if w is not None and self._len + n_new > w:
            drop = self._len + n_new - w                    # roll old rows out
        needed = self._len - drop + n_new
        if needed > self._cap:
            self._cap = max(self._cap * 2, needed)
            if w is not None:
                self._cap = min(self._cap, w)
            for name in self._buf:
                grown = np.empty(self._cap, dtype=self._dtypes[name])
                grown[: self._len] = self._buf[name][: self._len]
                self._buf[name] = grown
        for name in self._buf:
            buf = self._buf[name]
            if drop:
                buf[: self._len - drop] = buf[drop: self._len]
            buf[self._len - drop: needed] = arrays[name]
        self._len = needed

    # ── consumer side ──
    def version(self) -> int:
        return self._version

    def subscribe(self, cb: Callable[[Any], None]) -> Disposable:
        self._subs.append(cb)

        def unsubscribe() -> None:
            if cb in self._subs:
                self._subs.remove(cb)

        return Disposable(unsubscribe)

    def schema(self) -> Schema:
        return Schema(names=tuple(self._dtypes), kind="tabular",
                      dtypes=tuple(str(d) for d in self._dtypes.values()),
                      shape=(self._len, len(self._dtypes)))

    def size(self) -> int:
        return self._len

    def series(self, name: str) -> np.ndarray:
        if name not in self._buf:
            raise KeyError(f"no column {name!r}; available: {list(self._buf)}")
        with self._lock:
            return self._buf[name][: self._len].copy()      # torn-read-safe snapshot

    def resolve_channels(
        self, channels: dict[str, Any], *, who: str | None = None
    ) -> dict[str, np.ndarray]:
        """Snapshot the buffer under the lock, then resolve accessors against the
        copy — a render never sees a torn append, and later appends never mutate
        an already-resolved frame."""
        from .accessor import resolve_accessor  # noqa: PLC0415
        from .ref import check_channel_lengths  # noqa: PLC0415

        with self._lock:
            cols = {n: self._buf[n][: self._len].copy() for n in self._buf}
        out = {role: resolve_accessor(accessor, columns=cols, native=cols)
               for role, accessor in channels.items()}
        check_channel_lengths(out, who=who)
        return out

    def extent(self, name: str):
        from .ref import _numeric_extent  # noqa: PLC0415

        return _numeric_extent(self.series(name))

    def fingerprint(self):
        return (id(self), self._version)                    # identity churns per append

    def native(self) -> Any:
        return self


def stream(columns: dict[str, Any], *, window: int | None = None) -> StreamRef:
    """A live, append-able data source ([D76]): `stream({"t": float, "v": float},
    window=100_000)`. Bind it to any element like a dict/DataFrame; views on it
    update as you `append` (from any thread). `window` keeps the last N rows."""
    return StreamRef(columns, window=window)
