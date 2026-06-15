"""xarray 3-D cube → all instance lines for one sensor (a "spaghetti plot").

The input is a single `xarray.DataArray` with dims **(time, sensor, instance)** — the
shape you get logging several sensors across many runs/devices ("instances"). To inspect
one sensor you slice the cube and overlay every instance as its own line:

  1. `cube.sel(sensor="vibration")` — **label-based** select → a 2-D (time, instance) panel;
  2. `panel.isel(instance=i)` — each 1-D slice is recognized as **tabular** (x=`time`,
     y=the array name) and drawn as a `Curve`;
  3. overlay all instance curves (colored along a Viridis ramp), with the
     `panel.mean("instance")` envelope drawn bold on top.

One `xarray` object in; selection/reduction stay in xarray; qtviz draws the slices —
no manual reshaping to columns.

Scale: the cube is `10_000 × 4 × 250` (~10M samples); one sensor is **250 instances ×
10k timesteps ≈ 2.5M line points** overlaid as native pyqtgraph curves, drawn faint so
the overplotting reads as a density band with the mean envelope on top. (For an order of
magnitude more lines, route a single long-form line through `scale="datashader"` for a
line-density raster — see `examples/28_event_density_map.py` for the raster path.)

Run (needs the xarray extra):
    uv sync --extra xarray --extra dev
    uv run python examples/30_xarray_sensor_lines.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np

import qtviz as qv

SENSORS = ["temperature", "pressure", "humidity", "vibration"]
N_TIME = 10_000
N_INSTANCES = 250


def _cube():
    """A (time, sensor, instance) cube: per-sensor base signal + per-instance
    offset, slow drift, and noise (so instances spread around a common shape)."""
    import xarray as xr

    rng = np.random.default_rng(4)
    time = np.linspace(0.0, 24.0, N_TIME)
    bases = {
        "temperature": 21 + 5 * np.sin(2 * np.pi * time / 24),
        "pressure": 1013 + 3 * np.cos(2 * np.pi * time / 12),
        "humidity": 55 + 15 * np.sin(2 * np.pi * time / 24 + 1.0),
        "vibration": 0.5 + 0.4 * np.abs(np.sin(2 * np.pi * time / 6)),
    }
    cube = np.empty((N_TIME, len(SENSORS), N_INSTANCES))
    for s, name in enumerate(SENSORS):
        base = bases[name]
        scale = base.std() or 1.0
        for i in range(N_INSTANCES):
            offset = rng.normal(0, 0.12 * scale)
            drift = rng.normal(0, 0.06 * scale) * (time / time[-1])
            noise = rng.normal(0, 0.05 * scale, N_TIME)
            cube[:, s, i] = base + offset + drift + noise
    return xr.DataArray(
        cube, dims=("time", "sensor", "instance"),
        coords={"time": time, "sensor": SENSORS, "instance": np.arange(N_INSTANCES)},
        name="reading",
    )


def build(sensor: str = "vibration", theme: qv.Theme | None = None):
    panel = _cube().sel(sensor=sensor)                    # (time, instance), label select
    n = panel.sizes["instance"]
    ramp = qv.palettes.get("viridis")

    lines = [
        qv.Curve(panel.isel(instance=i), x="time", y="reading",
                 color=ramp.at(i / (n - 1)), line_width=0.8, alpha=0.35)
        for i in range(n)
    ]
    mean = qv.Curve(panel.mean("instance"), x="time", y="reading",
                    color="#ffffff", line_width=2.8)
    print(f"sensor {sensor!r}: {n} instances over {panel.sizes['time']} timesteps")

    return qv.View(qv.Overlay([*lines, mean]), theme=theme or qv.Theme.dark())


def main() -> int:
    if importlib.util.find_spec("xarray") is None:
        print("This example needs xarray: uv sync --extra xarray --extra dev")
        return 1
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    view = build()                                        # try sensor="temperature", etc.
    view.resize(960, 600)
    view.setWindowTitle("qtviz — xarray cube: all instances of one sensor")
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
