"""Capture PNG screenshots of every example for the docs.

Each example is run in its own subprocess: native examples under offscreen Qt,
webengine examples (13-20) on the real display (a QWebEngineView cannot render
headless — windows will appear briefly). The example's ``build()`` widget is
shown, the harness waits for every ``View`` to finish its (possibly async)
render plus a settle period, then saves ``widget.grab()`` to
``docs/images/examples/<name>.png``.

Run (from the repo root, with all extras synced):

    uv run python tools/capture_screenshots.py            # all examples
    uv run python tools/capture_screenshots.py 01 09 13   # by number prefix
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO / "examples"
OUT_DIR = REPO / "docs" / "images" / "examples"

# Per-example knobs: web=True → real display; settle=ms of extra event-loop
# time after all Views report a handle (async raster / page paint / streaming).
EXAMPLES: dict[str, dict] = {
    "01_hello": {},
    "02_composition": {},
    "03_backends": {},
    "04_theming": {"size": (1000, 620)},
    "05_interaction": {},
    "06_data_binding": {},
    "07_mixed_backends": {"size": (1000, 560)},
    "08_gallery": {"size": (1120, 780)},
    "09_datashader": {"settle": 1200},
    "10_out_of_core": {"settle": 1500},
    "11_datashader_matplotlib": {"settle": 3000},
    "12_color_mapping": {"size": (1000, 560)},
    "13_webengine": {"web": True, "settle": 4000},
    "14_webengine_overlay": {"web": True, "settle": 4000},
    "15_webengine_elements": {"web": True, "settle": 4000},
    "16_webengine_export": {"web": True, "settle": 4000},
    "17_webengine_heatmap": {"web": True, "settle": 4000},
    "18_webengine_raw_figure": {"web": True, "settle": 5000},
    "19_webengine_holoviews": {"web": True, "settle": 6000},
    "20_mixed_native_web": {"web": True, "settle": 5000, "size": (1100, 560),
                            "splitter": (550, 550)},
    "21_reactive_crossfilter": {"size": (1000, 560)},
    "22_from_holoviews": {"size": (1000, 560)},
    "23_from_holoviews_dynamicmap": {},
    "24_from_hvplot": {},
    "25_raster_inspect": {"settle": 1200},
    "26_telemetry_monitoring": {"size": (1000, 700)},
    "27_market_analytics": {"size": (1000, 700)},
    "28_event_density_map": {"settle": 1500, "size": (1000, 700)},
    "29_climate_field": {"settle": 3000, "size": (1000, 700)},
    "30_xarray_sensor_lines": {"settle": 4000},
    "31_axis_labels": {"size": (1000, 560)},
    "32_datashader_legends": {"settle": 1500, "size": (1100, 650)},
    "33_native_escape_hatch": {},
    "34_streaming_telemetry": {"settle": 1500, "size": (1200, 640), "splitter": (820, 380)},
    "35_everyday_figures": {"size": (1500, 760)},
    "dashboard_native": {"size": (1100, 700)},
}

DEFAULT_SIZE = (900, 600)
DEFAULT_SETTLE_MS = 1200
HANDLE_TIMEOUT_S = 90


# ── child: render one example and save the grab ──────────────────────────────

def _spin(app, ms: int) -> None:
    """Run the event loop for `ms` milliseconds (paints, timers, JS included)."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _looks_blank(pixmap) -> bool:
    """A grab that is one flat color (or nearly) means nothing rendered."""
    img = pixmap.toImage()
    w, h = img.width(), img.height()
    if w == 0 or h == 0:
        return True
    colors = {
        img.pixel(int(w * i / 60), int(h * j / 60))
        for i in range(1, 60)
        for j in range(1, 60)
    }
    return len(colors) < 6


def capture_one(name: str, out_path: Path) -> int:
    from PySide6.QtWidgets import QApplication, QWidget

    cfg = EXAMPLES[name]
    app = QApplication.instance() or QApplication([])

    spec = importlib.util.spec_from_file_location(name, EXAMPLES_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    built = mod.build()
    if isinstance(built, tuple):  # dashboard_native returns (view, selections)
        built = next(x for x in built if isinstance(x, QWidget))
    widget: QWidget = built
    widget.resize(*cfg.get("size", DEFAULT_SIZE))
    widget.show()

    if "splitter" in cfg:  # e.g. 34: default splitter sizes collapse a panel
        from PySide6.QtWidgets import QSplitter

        splitters = ([widget] if isinstance(widget, QSplitter)
                     else widget.findChildren(QSplitter))
        if splitters:
            splitters[0].setSizes(list(cfg["splitter"]))

    from qtviz.core.view import View

    views = ([widget] if isinstance(widget, View) else []) + widget.findChildren(View)
    deadline = time.monotonic() + HANDLE_TIMEOUT_S
    while time.monotonic() < deadline:
        _spin(app, 100)
        if all(v._handle is not None for v in views):
            break
    else:
        print(f"[{name}] timed out waiting for render handles", file=sys.stderr)

    _spin(app, cfg.get("settle", DEFAULT_SETTLE_MS))

    pixmap = widget.grab()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(out_path), "PNG"):
        print(f"[{name}] failed to save {out_path}", file=sys.stderr)
        return 1
    if _looks_blank(pixmap):
        print(f"[{name}] grab looks blank", file=sys.stderr)
        return 2
    print(f"[{name}] wrote {out_path} ({pixmap.width()}x{pixmap.height()})")
    return 0


# ── parent: one subprocess per example ───────────────────────────────────────

def run_all(selected: list[str]) -> int:
    names = [n for n in EXAMPLES if not selected or any(n.startswith(s) for s in selected)]
    failures: list[str] = []
    for name in names:
        env = os.environ.copy()
        if EXAMPLES[name].get("web"):
            env.pop("QT_QPA_PLATFORM", None)  # QWebEngineView needs a real display
        else:
            env["QT_QPA_PLATFORM"] = "offscreen"
        out = OUT_DIR / f"{name}.png"
        try:
            proc = subprocess.run(
                [sys.executable, __file__, "--one", name, "--out", str(out)],
                env=env, timeout=240,
            )
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = -1
            print(f"[{name}] subprocess timed out", file=sys.stderr)
        if rc != 0:
            failures.append(f"{name} (rc={rc})")
    print(f"\n{len(names) - len(failures)}/{len(names)} captured → {OUT_DIR}")
    if failures:
        print("failed: " + ", ".join(failures))
    return 1 if failures else 0


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["--one"]:
        name, out = argv[1], Path(argv[argv.index("--out") + 1])
        rc = capture_one(name, out)
        # Skip Qt teardown entirely — a QWebEngineView can crash on exit and
        # the PNG is already on disk.
        os._exit(rc)
    return run_all(argv)


if __name__ == "__main__":
    raise SystemExit(main())
