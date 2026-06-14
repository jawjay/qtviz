"""Tier-4 — webengine JSON transport baseline (W5; D29 "measured need").

Establishes the cost the Arrow transport (`design/webengine-arrow-transport.md`)
would replace: the time to serialize a native Scatter→Plotly figure to JSON, and
the JSON payload size vs the raw float64 floor (what a binary Arrow payload
approaches). Both are O(n), so the numbers extrapolate linearly — 10M ≈ 10× the
1M row.

Pure / headless — this is the Python half (serialize + payload size). The JS half
(transfer + `JSON.parse` + first paint) needs a live display and is a manual gate.

    pytest -m benchmark tests/qtviz/benchmarks/test_bench_webengine_transport.py
    python tests/qtviz/benchmarks/test_bench_webengine_transport.py
"""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.benchmark

SIZES = (100_000, 1_000_000)


def make_points(n: int) -> dict:
    import numpy as np

    rng = np.random.default_rng(0)
    return {"x": rng.random(n), "y": rng.random(n)}


def measure(n: int) -> dict:
    """Build the Scatter→Plotly figure and serialize it to JSON (the current
    bridge payload), against the raw float64 size (the binary floor)."""
    import plotly.io as pio

    import qtviz as qv
    from qtviz.backends.webengine import _figure

    points = make_points(n)
    t0 = time.perf_counter()
    fig, _ids = _figure.build(qv.Scatter(points, x="x", y="y"), qv.Theme.light())
    build_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    payload = pio.to_json(fig, validate=False)
    json_s = time.perf_counter() - t1

    json_bytes = len(payload.encode("utf-8"))
    raw_bytes = n * 2 * 8  # x + y as float64 — the binary (Arrow) floor
    return {
        "build_s": build_s,
        "json_s": json_s,
        "json_bytes": json_bytes,
        "raw_bytes": raw_bytes,
    }


def _report(rows: dict) -> None:
    print(
        f"\n  {'points':>11} {'build':>9} {'to_json':>9} {'json':>9} "
        f"{'raw':>8} {'inflate':>8} {'ns/pt':>7}"
    )
    for n, r in rows.items():
        print(
            f"  {n:>11,} {r['build_s'] * 1e3:7.0f}ms {r['json_s'] * 1e3:7.0f}ms "
            f"{r['json_bytes'] / 1e6:7.1f}MB {r['raw_bytes'] / 1e6:6.1f}MB "
            f"{r['json_bytes'] / r['raw_bytes']:6.1f}x {r['json_s'] / n * 1e9:6.0f}"
        )


# ── pytest entry point (opt-in via -m benchmark) ─────────────────────────────
def test_json_transport_baseline():
    pytest.importorskip("plotly")
    rows = {n: measure(n) for n in SIZES}
    _report(rows)
    top = rows[max(SIZES)]
    # The gap Arrow would close: JSON text is materially larger than the raw
    # float64 floor a binary payload approaches.
    assert top["json_bytes"] > top["raw_bytes"]


# ── standalone ───────────────────────────────────────────────────────────────
def main() -> int:
    try:
        import plotly.io  # noqa: F401
    except ImportError:
        print("plotly not available — install qtviz[webengine]")
        return 1
    print("webengine JSON transport baseline (Scatter → Plotly)")
    _report({n: measure(n) for n in SIZES})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
