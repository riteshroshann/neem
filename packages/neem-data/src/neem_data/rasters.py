"""Read remote cloud-optimised rasters straight onto a target grid."""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

from neem_core.grid import Grid
from neem_data.aoi import copernicus_tile, quadkey, to_wgs84
from neem_data.sources import CANOPY_TILE, CANOPY_ZOOM, DEM_TILE, GDAL_HTTP_ENV


def _warp(url: str, grid: Grid, resampling: Resampling, nodata: float) -> np.ndarray:
    """Warp one remote raster onto the grid; cells outside it get `nodata`."""
    with (
        rasterio.Env(**GDAL_HTTP_ENV),
        rasterio.open(f"/vsicurl/{url}") as src,
        WarpedVRT(
            src,
            crs=grid.crs,
            transform=Affine(*grid.transform),
            width=grid.cols,
            height=grid.rows,
            resampling=resampling,
            src_nodata=src.nodata,
            nodata=nodata,
        ) as vrt,
    ):
        return vrt.read(1, out_dtype="float32")


def _corners_latlon(grid: Grid) -> list[tuple[float, float]]:
    minx, miny, maxx, maxy = grid.bounds
    lons, lats = to_wgs84().transform([minx, maxx, minx, maxx], [miny, miny, maxy, maxy])
    return list(zip(lats, lons, strict=True))


def read_dem(grid: Grid) -> np.ndarray:
    tiles = {copernicus_tile(lat, lon) for lat, lon in _corners_latlon(grid)}
    out = np.full(grid.shape, np.nan, dtype=np.float32)
    for tile in sorted(tiles):
        part = _warp(DEM_TILE.format(tile=tile), grid, Resampling.bilinear, np.nan)
        out = np.where(np.isnan(out), part, out)
    if np.isnan(out).any():
        raise ValueError("DEM does not cover the grid")
    return out


def read_canopy(grid: Grid) -> np.ndarray:
    """Canopy height above ground in metres; 0 where there is no tree or no data."""
    tiles = {quadkey(lat, lon, CANOPY_ZOOM) for lat, lon in _corners_latlon(grid)}
    out = np.zeros(grid.shape, dtype=np.float32)
    for qk in sorted(tiles):
        part = _warp(CANOPY_TILE.format(quadkey=qk), grid, Resampling.bilinear, 0.0)
        np.maximum(out, np.nan_to_num(part, nan=0.0), out=out)
    return out
