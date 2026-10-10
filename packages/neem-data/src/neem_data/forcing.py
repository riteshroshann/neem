"""Bridge pipeline weather files to the core's MetHour and Site."""

from __future__ import annotations

from datetime import datetime

import geopandas as gpd

from neem_core.met import MetHour, Site
from neem_core.scene import Scene
from neem_data import lake
from neem_data.aoi import IST_OFFSET
from neem_data.weather import load_day


def showcase_day() -> str:
    return lake.path("raw", "met", "showcase.txt").read_text().strip()


def met_hours(day: str, first: int = 0, last: int = 23) -> list[MetHour]:
    out = []
    for h in load_day(lake.path("raw", "met", f"{day}.json")):
        t = datetime.fromisoformat(h.time)
        if first <= t.hour <= last:
            out.append(
                MetHour(t, h.ta, h.rh, h.global_rad, h.direct_rad, h.diffuse_rad, h.ws, h.pressure)
            )
    return out


def site_for(scene: Scene) -> Site:
    minx, miny, maxx, maxy = scene.grid.bounds
    centre = gpd.GeoSeries.from_xy([(minx + maxx) / 2], [(miny + maxy) / 2], crs=scene.grid.crs)
    p = centre.to_crs("EPSG:4326").iloc[0]
    return Site(
        latitude=float(p.y),
        longitude=float(p.x),
        altitude=float(scene.dem.mean()),
        utc_offset=IST_OFFSET,
    )
