"""Tier-4 — webengine Plotly transport (W5; D29 "measured need").

Compares the two serializations of a native Scatter→Plotly figure:
- **lists → JSON text** — the pre-W5.1a path (`.tolist()` arrays);
- **numpy → go.Figure → base64** — W5.1a: Plotly's own typed-array encoder emits
  `{dtype, bdata}` once the figure is a `go.Figure` with numpy arrays.

…against the raw float64 floor (what a true-binary Arrow payload approaches). Both
are O(n), so the numbers extrapolate linearly. Pure / headless — the JS-side decode
+ paint needs a live display and is a manual gate.

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
_BDATA = '"bdata"'


def make_points(n: int) -> dict:
    import numpy as np

    rng = np.random.default_rng(0)
    return {"x": rng.random(n), "y": rng.random(n)}


def measure(n: int) -> dict:
    import numpy as np
    import plotly.graph_objects as go
    import plotly.io as pio

    import qtviz as qv
    from qtviz.backends.webengine import _figure

    t0 = time.perf_counter()
    fig, _ids = _figure.build(qv.Scatter(make_points(n), x="x", y="y"), qv.Theme.light())
    build_s = time.perf_counter() - t0

    trace = fig["data"][0]
    as_lists = {**trace, "x": np.asarray(trace["x"]).tolist(), "y": np.asarray(trace["y"]).tolist()}
    lists_fig = {"data": [as_lists], "layout": fig["layout"]}
    t = time.perf_counter()
    js_lists = pio.to_json(lists_fig, validate=False)
    lists_s = time.perf_counter() - t

    t = time.perf_counter()
    js_b64 = pio.to_json(go.Figure(fig), validate=False)  # the path PlotlyBackend takes
    b64_s = time.perf_counter() - t

    return {
        "build_s": build_s,
        "lists_s": lists_s, "lists_bytes": len(js_lists.encode("utf-8")),
        "b64_s": b64_s, "b64_bytes": len(js_b64.encode("utf-8")), "b64_used": _BDATA in js_b64,
        "raw_bytes": n * 2 * 8,
    }


def _report(rows: dict) -> None:
    print(f"\n  {'points':>11} {'build':>7} | {'lists':>8} {'MB':>6} | {'base64':>8} {'MB':>6} "
          f"| {'raw MB':>7} {'speedup':>8} {'b64?':>5}")
    for n, r in rows.items():
        print(
            f"  {n:>11,} {r['build_s'] * 1e3:5.0f}ms | "
            f"{r['lists_s'] * 1e3:6.0f}ms {r['lists_bytes'] / 1e6:5.1f} | "
            f"{r['b64_s'] * 1e3:6.0f}ms {r['b64_bytes'] / 1e6:5.1f} | "
            f"{r['raw_bytes'] / 1e6:6.1f} {r['lists_s'] / r['b64_s']:7.1f}x {str(r['b64_used']):>5}"
        )


# ── pytest entry point (opt-in via -m benchmark) ─────────────────────────────
def test_plotly_transport_baseline():
    pytest.importorskip("plotly")
    rows = {n: measure(n) for n in SIZES}
    _report(rows)
    top = rows[max(SIZES)]
    assert top["b64_used"], "W5.1a regression: figure no longer base64-encodes"
    assert top["b64_bytes"] < top["lists_bytes"]  # base64 is smaller than JSON text


# ── standalone ───────────────────────────────────────────────────────────────
def main() -> int:
    try:
        import plotly.io  # noqa: F401
    except ImportError:
        print("plotly not available — install qtviz[webengine]")
        return 1
    print("webengine Plotly transport — lists(JSON) vs numpy(go.Figure→base64)")
    _report({n: measure(n) for n in SIZES})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
