"""Read side: the ranking, school twins and compact binary layers for the browser."""

from __future__ import annotations

import json
from functools import cache
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from neem_core.scene import Scene
from neem_data import lake

LAYER_HOURS = (7, 13)  # the morning shift; enough for the planner and keeps payloads small


@cache
def schools() -> gpd.GeoDataFrame:
    df = gpd.read_parquet(lake.path(*lake.SCHOOLS))
    centroids = df.to_crs("EPSG:32643").centroid.to_crs("EPSG:4326")
    df["lat"] = centroids.y.round(6)
    df["lon"] = centroids.x.round(6)
    return df


def ranking(day: str) -> pd.DataFrame:
    path = lake.path("rank", day, "schools.parquet")
    if not path.exists():
        return pd.DataFrame()
    rank = pd.read_parquet(path)
    rank = rank[rank["status"] == "ok"].drop(columns=["error", "trace"], errors="ignore")
    geo = schools()[["school_id", "lat", "lon"]]
    return rank.merge(pd.DataFrame(geo), on="school_id", how="left")


def has_twin(school_id: str, day: str) -> bool:
    return (lake.run_dir(school_id, f"{day}-base") / "meta.json").exists()


def twin_summary(school_id: str, day: str) -> dict[str, Any]:
    run = lake.run_dir(school_id, f"{day}-base")
    meta = json.loads((run / "meta.json").read_text())
    scene = Scene.load(lake.scene_dir(school_id))
    hours = [h for h in meta["hours"] if LAYER_HOURS[0] <= int(h["time"][11:13]) <= LAYER_HOURS[1]]
    return {
        "school_id": school_id,
        "name": meta["name"],
        "day": day,
        "site": meta["site"],
        "grid": {
            "rows": scene.grid.rows,
            "cols": scene.grid.cols,
            "pixel_size": scene.grid.pixel_size,
            "x0": scene.grid.x0,
            "y0": scene.grid.y0,
            "crs": scene.grid.crs,
        },
        "hours": hours,
        "exposure": meta["exposure"],
        "quality": meta["quality"],
        "calibration_mae_changed": meta.get("calibration_mae_changed"),
        "timings": meta["timings"],
        "provenance": meta["provenance"],
        "layers": layer_index(scene, len(hours)),
    }


def layer_index(scene: Scene, n_hours: int) -> list[dict[str, Any]]:
    """Byte layout of /layers.bin. Every layer is little-endian int16, value = int / scale."""
    cells = scene.grid.rows * scene.grid.cols
    spec = [
        ("dsm", 1, 100),
        ("dem", 1, 100),
        ("cdsm", 1, 100),
        ("svf", 1, 10000),
        ("zones", 1, 1),
        ("tmrt", n_hours, 100),
        ("utci", n_hours, 100),
    ]
    out, offset = [], 0
    for name, count, scale in spec:
        out.append(
            {
                "name": name,
                "count": count,
                "scale": scale,
                "offset": offset,
                "dtype": "int16",
                "ref": "dem_min" if name in ("dsm", "dem") else None,
            }
        )
        offset += count * cells * 2
    return out


def layers_bin(school_id: str, day: str) -> tuple[bytes, float]:
    """The binary payload and the height reference (minimum DEM) for dsm/dem."""
    run = lake.run_dir(school_id, f"{day}-base")
    scene = Scene.load(lake.scene_dir(school_id))
    meta = json.loads((run / "meta.json").read_text())
    keep = [
        i
        for i, h in enumerate(meta["hours"])
        if LAYER_HOURS[0] <= int(h["time"][11:13]) <= LAYER_HOURS[1]
    ]
    with np.load(run / "field.npz") as f:
        tmrt = f["tmrt"].astype(np.float32)[keep]
        utci = f["utci"].astype(np.float32)[keep]
        svf = f["svf"].astype(np.float32)
    ref = float(scene.dem.min())

    def q(a: np.ndarray, scale: float) -> bytes:
        return np.clip(np.round(np.nan_to_num(a) * scale), -32768, 32767).astype("<i2").tobytes()

    parts = [
        q(scene.dsm - ref, 100),
        q(scene.dem - ref, 100),
        q(scene.cdsm, 100),
        q(svf, 10000),
        q(scene.zones.astype(np.float32), 1),
        q(tmrt, 100),
        q(utci, 100),
    ]
    return b"".join(parts), ref


def calibration(school_id: str, day: str) -> dict[str, Any]:
    cal = json.loads((lake.run_dir(school_id, f"{day}-base") / "calibration.json").read_text())
    cal["hours"] = [
        h for h in cal["hours"] if LAYER_HOURS[0] <= int(h["label"][:2]) <= LAYER_HOURS[1]
    ]
    return cal


def child(school_id: str, day: str) -> dict[str, Any]:
    return json.loads((lake.run_dir(school_id, f"{day}-base") / "child.json").read_text())
