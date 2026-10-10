"""Delhi schools from OpenStreetMap, with their grounds where mapped."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from neem_data.http import post_json
from neem_data.sources import OVERPASS

QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="IN-DL"]->.delhi;
(
  way["amenity"="school"](area.delhi);
  relation["amenity"="school"](area.delhi);
  node["amenity"="school"](area.delhi);
);
out tags geom;
"""

# Delhi government and municipal school naming conventions
_GOVT = re.compile(
    r"\b(govt|government|sarvodaya|rajkiya|gbsss|ggsss|gsss|gss|sbv|skv|rpvv|mcd|ndmc|nigam|"
    r"kendriya vidyalaya|navodaya|dte|doe|school of specialised excellence|sose)\b",
    re.IGNORECASE,
)


def is_government(tags: dict[str, str]) -> bool:
    operator_type = tags.get("operator:type", "").lower()
    if operator_type in ("government", "public"):
        return True
    if operator_type in ("private", "religious"):
        return False
    text = " ".join(tags.get(k, "") for k in ("name", "name:en", "operator", "official_name"))
    return bool(_GOVT.search(text))


def _ring(geometry: list[dict[str, float]]) -> list[tuple[float, float]]:
    return [(p["lon"], p["lat"]) for p in geometry]


def _shape(el: dict[str, Any]) -> Polygon | MultiPolygon | Point | None:
    if el["type"] == "node":
        return Point(el["lon"], el["lat"])
    if el["type"] == "way":
        ring = _ring(el.get("geometry", []))
        return Polygon(ring) if len(ring) >= 4 and ring[0] == ring[-1] else None
    outers = [
        Polygon(_ring(m["geometry"]))
        for m in el.get("members", [])
        if m.get("role") == "outer" and len(m.get("geometry", [])) >= 4
    ]
    if not outers:
        return None
    merged = unary_union(outers)
    return merged if isinstance(merged, Polygon | MultiPolygon) else None


BOUNDARY_QUERY = '[out:json][timeout:120];relation["ISO3166-2"="IN-DL"];out geom;'


def fetch_boundary(out: Path, tolerance_deg: float = 0.002) -> int:
    """Delhi NCT outline as simplified GeoJSON, for the site's map. Returns vertex count."""
    import json

    from shapely.geometry import LineString
    from shapely.ops import linemerge, polygonize

    payload = post_json(OVERPASS, data={"data": BOUNDARY_QUERY})
    rel = payload["elements"][0]
    # A big boundary is many open ways; stitch them before closing rings.
    lines = [
        LineString(_ring(m["geometry"]))
        for m in rel.get("members", [])
        if m.get("role") == "outer" and len(m.get("geometry", [])) >= 2
    ]
    polys = list(polygonize(linemerge(lines)))
    if not polys:
        raise ValueError("no Delhi boundary in the Overpass response")
    simple = unary_union(polys).simplify(tolerance_deg, preserve_topology=True)
    out.write_text(json.dumps(simple.__geo_interface__))
    polys = list(getattr(simple, "geoms", [simple]))
    return sum(len(p.exterior.coords) for p in polys)


def fetch_schools(out: Path) -> gpd.GeoDataFrame:
    payload = post_json(OVERPASS, data={"data": QUERY})
    rows = []
    for el in payload["elements"]:
        shape = _shape(el)
        if shape is None or not shape.is_valid:
            continue
        tags: dict[str, str] = el.get("tags", {})
        rows.append(
            {
                "school_id": f"osm-{el['type'][0]}{el['id']}",
                "name": tags.get("name:en") or tags.get("name") or "Unnamed school",
                "name_hi": tags.get("name:hi"),
                "government": is_government(tags),
                "has_grounds": el["type"] != "node",
                "isced": tags.get("isced:level"),
                "geometry": shape,
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    area = gdf.to_crs("EPSG:32643").area
    gdf["area_m2"] = area.where(gdf["has_grounds"], 0.0).round(0)
    gdf.to_parquet(out)
    print(
        f"osm: {len(gdf):,} schools, {int(gdf.has_grounds.sum()):,} with grounds, "
        f"{int(gdf.government.sum()):,} government -> {out}"
    )
    return gdf
