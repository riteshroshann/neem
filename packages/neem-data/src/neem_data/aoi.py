"""Area of interest and coordinate plumbing."""

from __future__ import annotations

import math
from functools import cache

from pyproj import Transformer

from neem_core.grid import UTM43N

# Delhi NCT with a small margin, (min_lon, min_lat, max_lon, max_lat)
DELHI_BBOX = (76.83, 28.40, 77.35, 28.89)
DELHI_LATLON = (28.6139, 77.2090)
IST_OFFSET = 5.5


@cache
def to_utm() -> Transformer:
    return Transformer.from_crs("EPSG:4326", UTM43N, always_xy=True)


@cache
def to_wgs84() -> Transformer:
    return Transformer.from_crs(UTM43N, "EPSG:4326", always_xy=True)


def quadkey(lat: float, lon: float, zoom: int) -> str:
    """Bing-style quadkey of the web-mercator tile containing a point."""
    x = (lon + 180.0) / 360.0
    s = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    n = 2**zoom
    tx, ty = min(int(x * n), n - 1), min(int(y * n), n - 1)
    digits = []
    for i in range(zoom, 0, -1):
        mask = 1 << (i - 1)
        digits.append(str((1 if tx & mask else 0) + (2 if ty & mask else 0)))
    return "".join(digits)


def copernicus_tile(lat: float, lon: float) -> str:
    """Name of the Copernicus GLO-30 tile containing a point (northern, eastern hemisphere)."""
    return f"Copernicus_DSM_COG_10_N{math.floor(lat):02d}_00_E{math.floor(lon):03d}_00_DEM"
