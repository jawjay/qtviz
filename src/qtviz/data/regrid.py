"""Viewport regrid — window + decimate + shade a lazy grid ([D75]).

The gridded sibling of `ext.datashader.themed_rasterize`: a `rasterize`
function the shared `RasterController` can drive, so a huge zarr / dask /
xarray grid re-reads only the visible window at widget resolution on pan/zoom
and *sharpens* instead of pixelating. Pure data + numpy — no Qt, no optional
imports beyond what the ref itself uses.

Coordinate model: the rendered `Image` places its raster by `element.extent`
(data space); the array itself is indexed. `make_regrid` closes over the bounds
and maps viewport data-coords ⇄ array indices linearly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RegridResult:
    """Mirror of the datashader RasterResult the RasterController consumes."""

    rgba: np.ndarray                                  # (h, w, 4) uint8, row 0 = ymin
    bounds: tuple[float, float, float, float]         # data-space (x0, y0, x1, y1)
    aggregate: np.ndarray                             # the visible values window
    legend: object                                    # truthful window-range colorbar


def shade_values(values, palette, title: str | None = None):
    """A 2-D values grid → (uint8 rgba, continuous `Legend`) through the shared
    encoding LUT — the same ramp/legend rule as a native `color_by`, so a
    regridded array matches the rest of the library."""
    from ..core.encoding import map_colors  # noqa: PLC0415

    a = np.asarray(values, dtype="float64")
    rgba01, legend = map_colors(a.ravel(), palette=palette, continuous_palette=palette,
                                kind="continuous", title=title)
    rgba = (rgba01.reshape(*a.shape, 4) * 255.0).round().astype(np.uint8)
    return rgba, legend


def make_regrid(bounds, palette, title: str | None = None):
    """A `rasterize(ref, *, width, height, x_range, y_range) -> RegridResult`
    for the RasterController: viewport → index window (`ref.window`) →
    decimated read at ~widget resolution (`materialize(max_cells)`) → shaded
    rgba + a legend whose vmin/vmax track the *visible* values (C3)."""
    bx0, by0, bx1, by1 = (float(v) for v in bounds)
    span_x, span_y = (bx1 - bx0) or 1.0, (by1 - by0) or 1.0

    def rasterize(ref, *, width: int, height: int, x_range, y_range) -> RegridResult:
        ny, nx = ref.schema().shape[:2]
        lo_x, hi_x = sorted(((x_range[0] - bx0) / span_x, (x_range[1] - bx0) / span_x))
        lo_y, hi_y = sorted(((y_range[0] - by0) / span_y, (y_range[1] - by0) / span_y))
        x0 = int(np.clip(np.floor(lo_x * nx), 0, nx - 1))
        x1 = int(np.clip(np.ceil(hi_x * nx), x0 + 1, nx))
        y0 = int(np.clip(np.floor(lo_y * ny), 0, ny - 1))
        y1 = int(np.clip(np.ceil(hi_y * ny), y0 + 1, ny))
        eager = ref.window(x=(x0, x1), y=(y0, y1)).materialize(
            max_cells=max(1, int(width) * int(height))
        )
        values = np.asarray(eager.grid().values)
        rgba, legend = shade_values(values, palette, title)
        window_bounds = (bx0 + x0 / nx * span_x, by0 + y0 / ny * span_y,
                         bx0 + x1 / nx * span_x, by0 + y1 / ny * span_y)
        return RegridResult(rgba=rgba, bounds=window_bounds,
                            aggregate=values, legend=legend)

    return rasterize
