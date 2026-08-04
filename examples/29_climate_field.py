"""Gridded scientific field — an xarray 2-D field plus a cross-section profile.

Hand qtviz an `xarray.DataArray` directly: a 2-D array (here a synthetic temperature
anomaly over a lon/lat grid) is recognized as **gridded** data and drawn as an `Image`
over its geographic bounds. A 1-D `da.isel(...)` slice is recognized as **tabular** and
drawn as a `Curve` — the same library, two data shapes, no manual conversion.

The map and the cross-section share an X axis (`link_x`), so panning the longitude on
one moves the other; the profile is the field sampled along a single latitude.

Run (needs the xarray extra):
    uv sync --extra xarray --extra dev
    uv run python examples/29_climate_field.py
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np

import qtviz as qv


def _field():
    import xarray as xr

    lon = np.linspace(-10.0, 40.0, 220)
    lat = np.linspace(35.0, 70.0, 160)
    lon_g, lat_g = np.meshgrid(lon, lat)                      # (nlat, nlon)
    rng = np.random.default_rng(0)
    field = (
        0.04 * (lon_g + 10) - 0.06 * (lat_g - 35)             # broad gradient
        + 4.0 * np.exp(-(((lon_g - 12) ** 2 + (lat_g - 55) ** 2) / 40))   # warm anomaly
        - 3.0 * np.exp(-(((lon_g - 28) ** 2 + (lat_g - 45) ** 2) / 30))   # cool anomaly
        + rng.normal(0, 0.3, lon_g.shape)
    )
    return xr.DataArray(field, dims=("lat", "lon"),
                        coords={"lat": lat, "lon": lon}, name="temp_anomaly")


def build(theme: qv.Theme | None = None):
    da = _field()
    lon, lat = da["lon"].values, da["lat"].values

    field_map = qv.Image(da, extent=(lon[0], lat[0], lon[-1], lat[-1]), colormap="magma")

    cut = int(np.argmin(np.abs(lat - 55.0)))                  # cross-section at ~55°N
    profile = da.isel(lat=cut)                                # 1-D over lon → tabular
    section = qv.Curve(profile, x="lon", y="temp_anomaly", color="#ff7f0e", line_width=2.0)
    print(f"cross-section at lat={lat[cut]:.1f}°N")

    layout = qv.Layout([field_map, section], options=qv.LayoutOptions(rows=2, link_x=True))
    return qv.View(layout, theme=theme or qv.Theme.dark())


def main() -> int:
    if importlib.util.find_spec("xarray") is None:
        print("This example needs xarray: uv sync --extra xarray --extra dev")
        return 1
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    view = build()
    view.resize(900, 760)
    view.setWindowTitle("qtviz — gridded field + cross-section")
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
