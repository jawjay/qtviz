"""Bridge round-trip latency benchmark.

Measures Python -> JS -> Python round-trip time for various payload sizes.
Useful for spotting regressions and deciding whether throttling / a binary
fast-path is worth adding.

Run:
    uv run python tools/bench_bridge.py
"""

from __future__ import annotations

import statistics
import sys
from typing import Any

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from qtwebplot import WebBridgeView

PAGE = """
<!doctype html>
<html><head></head><body>
<script>
qtwebplot.onReady(function () {
  qtwebplot.on("ping", function (p) { qtwebplot.send("pong", p); });
  qtwebplot.send("bench.ready", {});
});
</script>
</body></html>
"""


def wait_for_signal(signal, timeout_ms: int = 10_000) -> bool:
    """Spin a local QEventLoop until `signal` fires or we time out."""
    loop = QEventLoop()
    signal.connect(loop.quit)
    timed_out = {"v": False}

    def _on_timeout() -> None:
        timed_out["v"] = True
        loop.quit()

    QTimer.singleShot(timeout_ms, _on_timeout)
    loop.exec()
    return not timed_out["v"]


class _Roundtripper:
    """Send `n` sequential ping/pong pairs and record the times."""

    def __init__(self, view: WebBridgeView, payload: Any, n: int) -> None:
        self.view = view
        self.payload = payload
        self.n = n
        self.times: list[float] = []
        self._t0 = 0.0
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._loop = QEventLoop()
        view.received.connect(self._on_recv)

    def _on_recv(self, name: str, _payload: Any) -> None:
        if name != "pong":
            return
        # Use Qt's monotonic clock via QElapsedTimer-equivalent: time.monotonic
        import time as _t

        dt = _t.monotonic() - self._t0
        self.times.append(dt)
        if len(self.times) < self.n:
            self._send_one()
        else:
            self.view.received.disconnect(self._on_recv)
            self._loop.quit()

    def _send_one(self) -> None:
        import time as _t

        self._t0 = _t.monotonic()
        self.view.send("ping", self.payload)

    def run(self) -> list[float]:
        self._send_one()
        # Safety bound: 30s for any single benchmark.
        QTimer.singleShot(30_000, self._loop.quit)
        self._loop.exec()
        return self.times


def make_payload(n_bytes: int) -> Any:
    if n_bytes == 0:
        return None
    # A predictable shape: dict with one large string field.
    return {"blob": "x" * n_bytes, "size": n_bytes}


def fmt(seconds: list[float]) -> str:
    if not seconds:
        return "no samples"
    ms = sorted(s * 1000 for s in seconds)
    median = statistics.median(ms)
    p95 = ms[int(len(ms) * 0.95) - 1] if len(ms) > 1 else ms[0]
    mean = statistics.mean(ms)
    return (
        f"n={len(ms):4d}  "
        f"median={median:7.3f}ms  "
        f"mean={mean:7.3f}ms  "
        f"p95={p95:7.3f}ms  "
        f"min={ms[0]:7.3f}ms  max={ms[-1]:7.3f}ms"
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    view = WebBridgeView()
    view.resize(400, 200)
    view.show()

    print("Loading bench page...", file=sys.stderr)
    view.load_html(PAGE)
    if not wait_for_signal(view.ready, timeout_ms=10_000):
        print("ERROR: bridge never became ready", file=sys.stderr)
        return 1
    print("Bridge ready.", file=sys.stderr)

    sizes = [0, 256, 4096, 65_536, 524_288]  # 0B, 256B, 4KB, 64KB, 512KB
    samples_per_size = 200
    warmup = 20

    print()
    print(f"Round-trip latency over {samples_per_size} samples (after {warmup} warmup)")
    print("=" * 90)

    for size in sizes:
        payload = make_payload(size)
        # Warmup
        _Roundtripper(view, payload, warmup).run()
        # Measure
        times = _Roundtripper(view, payload, samples_per_size).run()
        label = f"{size:>7} B"
        print(f"  payload={label}   {fmt(times)}")

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
