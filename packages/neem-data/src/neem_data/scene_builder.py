"""Turn one school's open data into a 1 m scene: DSM, DEM, canopy and zones."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import duckdb
import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine
from shapely.geometry.base import BaseGeometry

from neem_core.grid import UTM43N, Grid
from neem_core.scene import ZONE_BUILDING, ZONE_GROUND, ZONE_NONE, Scene
from neem_data import lake
from neem_data.rasters import read_canopy, read_dem
from neem_data.sources import CANOPY_VERSION, OVERTURE_RELEASE

MARGIN_M = 40.0  # neighbours within this distance can shade the yard
MIN_CANOPY_M = 2.0  # below this the canopy model is mostly grass, cars and noise
STOREY_M = 3.2


@dataclass(frozen=True, slots=True)
class BuildQuality:
    buildings: int
    with_height: int  # measured or from floor count
    canopy_cover: float  # fraction of open school ground under canopy

    @property
    def height_coverage(self) -> float:
        return self.with_height / self.buildings if self.buildings else 1.0


def footprint_height(area_m2: float) -> float:
    """Height prior for a Delhi footprint with no height or floor count."""
    if area_m2 < 50:
        return 3.5  # sheds, guard rooms
    if area_m2 < 300:
        return 9.0  # typical G+2 house
    if area_m2 < 1500:
        return 12.0  # school blocks, small flats
    return 15.0


@cache
def _schools() -> gpd.GeoDataFrame:
    return gpd.read_parquet(lake.path(*lake.SCHOOLS))


def school_row(school_id: str) -> dict[str, Any]:
    df = _schools()
    hit = df[df.school_id == school_id]
    if hit.empty:
        raise KeyError(f"unknown school {school_id}")
    return hit.iloc[0].to_dict()


def grid_for(geom_utm: BaseGeometry, pixel_size: float) -> Grid:
    minx, miny, maxx, maxy = geom_utm.buffer(MARGIN_M).bounds
    x0 = math.floor(minx / pixel_size) * pixel_size
    y0 = math.ceil(maxy / pixel_size) * pixel_size
    cols = math.ceil((maxx - x0) / pixel_size)
    rows = math.ceil((y0 - miny) / pixel_size)
    return Grid(x0=x0, y0=y0, pixel_size=pixel_size, rows=rows, cols=cols, crs=UTM43N)


def buildings_in(grid: Grid, path: Path | None = None) -> gpd.GeoDataFrame:
    from neem_data.aoi import to_wgs84

    minx, miny, maxx, maxy = grid.bounds
    lons, lats = to_wgs84().transform([minx, maxx], [miny, maxy])
    src = (path or lake.path(*lake.BUILDINGS)).as_posix()
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    df = con.execute(
        f"""
        SELECT id, height, num_floors, ST_AsWKB(geometry) AS wkb
        FROM '{src}'
        WHERE ST_Intersects(geometry, ST_MakeEnvelope({lons[0]}, {lats[0]}, {lons[1]}, {lats[1]}))
        """
    ).df()
    geoms = gpd.GeoSeries.from_wkb(df.pop("wkb").map(bytes), crs="EPSG:4326")
    return gpd.GeoDataFrame(df, geometry=geoms, crs="EPSG:4326").to_crs(UTM43N)


def resolve_heights(b: gpd.GeoDataFrame) -> tuple[np.ndarray, int]:
    """Measured height, else floors x storey, else a footprint prior. Returns (heights, known)."""
    measured = b["height"].to_numpy(dtype=float, na_value=np.nan)
    floors = b["num_floors"].to_numpy(dtype=float, na_value=np.nan) * STOREY_M
    prior = np.array([footprint_height(a) for a in b.geometry.area])
    h = np.where(np.isfinite(measured), measured, np.where(np.isfinite(floors), floors, prior))
    known = int((np.isfinite(measured) | np.isfinite(floors)).sum())
    return np.clip(h, 2.5, 120.0), known


def build_scene(school_id: str, pixel_size: float = 1.0) -> tuple[Scene, BuildQuality]:
    row = school_row(school_id)
    geom = gpd.GeoSeries([row["geometry"]], crs="EPSG:4326").to_crs(UTM43N).iloc[0]
    grid = grid_for(geom, pixel_size)
    transform = Affine(*grid.transform)

    dem = read_dem(grid)
    canopy = read_canopy(grid)

    b = buildings_in(grid)
    heights, known = resolve_heights(b)
    order = np.argsort(heights)  # taller buildings drawn last win
    bh = np.zeros(grid.shape, dtype=np.float32)
    if len(b):
        bh = np.asarray(
            rasterize(
                ((b.geometry.iloc[i], float(heights[i])) for i in order),
                out_shape=grid.shape,
                transform=transform,
                fill=0,
                dtype="float32",
            ),
            dtype=np.float32,
        )

    on_building = bh > 0
    cdsm = np.where(on_building | (canopy < MIN_CANOPY_M), 0.0, np.minimum(canopy, 30.0))
    inside = np.asarray(
        rasterize([(geom, 1)], out_shape=grid.shape, transform=transform, fill=0, dtype="uint8")
    ).astype(bool)
    zones = np.full(grid.shape, ZONE_NONE, dtype=np.uint8)
    zones[inside & ~on_building] = ZONE_GROUND
    zones[inside & on_building] = ZONE_BUILDING

    ground = zones == ZONE_GROUND
    cover = float((cdsm[ground] > 0).mean()) if ground.any() else 0.0
    scene = Scene(
        school_id=school_id,
        name=str(row["name"]),
        grid=grid,
        dsm=(dem + bh).astype(np.float32),
        dem=dem.astype(np.float32),
        cdsm=cdsm.astype(np.float32),
        zones=zones,
        provenance={
            "overture": OVERTURE_RELEASE,
            "canopy": CANOPY_VERSION,
            "dem": "copernicus-glo30",
            "osm_school": school_id,
        },
    )
    return scene, BuildQuality(buildings=len(b), with_height=known, canopy_cover=cover)
