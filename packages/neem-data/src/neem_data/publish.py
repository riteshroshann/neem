"""Export what the static site needs: ranking, twins index, palette and heat thumbnails."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image

from neem_core.met import MetHour, Site
from neem_core.palette import (
    NEARBY_ROOF,
    OUTSIDE_ALPHA,
    SCHOOL_ROOF,
    TALL_M,
    colorize,
    hex_to_rgb,
    to_json,
)
from neem_core.scene import ZONE_BUILDING, ZONE_GROUND
from neem_core.sun import subsolar_point, sun_position
from neem_data import lake

# maps are drawn on transparent ground so they sit on whatever paper the site uses
SCHOOL_RGBA = (*hex_to_rgb(SCHOOL_ROOF), 255)
NEARBY_RGBA = (*hex_to_rgb(NEARBY_ROOF), 255)
THUMB_PX = 96
SHOWCASE = "osm-w1321574340"  # Kendriya Vidyalaya, Sector 25, Rohini


def thumbnail(src: Path, dst: Path) -> None:
    with np.load(src) as z:
        utci, zones = z["utci"].astype(np.float32), z["zones"]
    rgb = np.dstack([colorize(utci), np.full(utci.shape, 255, np.uint8)])
    rgb[zones == ZONE_BUILDING] = SCHOOL_RGBA
    rgb[(zones != ZONE_GROUND) & (zones != ZONE_BUILDING)] = 0
    rows, cols = np.nonzero(zones)
    if len(rows):  # crop to the school, keep it square
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        side = max(r1 - r0, c1 - c0)
        rc, cc = (r0 + r1) // 2, (c0 + c1) // 2
        r0, c0 = max(0, rc - side // 2), max(0, cc - side // 2)
        rgb = rgb[r0 : r0 + side, c0 : c0 + side]
    img = Image.fromarray(rgb).resize((THUMB_PX, THUMB_PX), Image.Resampling.NEAREST)
    img.save(dst, optimize=True)


def field_at(run: Path, hour: str, kind: str = "utci") -> np.ndarray:
    with np.load(run / "field.npz") as f:
        hours = [str(t)[11:16] for t in f["hours"]]
        return f[kind][hours.index(hour)].astype(np.float32)


def heat_png(school_id: str, run_id: str, dst: Path) -> None:
    """The 1 pm heat map as an image, painted like the planner canvas: the instant first view."""
    from neem_core.scene import Scene

    scene = Scene.load(lake.scene_dir(school_id))
    utci = field_at(lake.run_dir(school_id, run_id), "13:00")
    rgba = np.dstack([colorize(utci), np.full(utci.shape, 255, np.uint8)])
    rgba[scene.zones != ZONE_GROUND, 3] = OUTSIDE_ALPHA
    rgba[(scene.dsm - scene.dem) > TALL_M] = NEARBY_RGBA
    rgba[scene.zones == ZONE_BUILDING] = SCHOOL_RGBA
    Image.fromarray(rgba).save(dst, optimize=True)


def open_yard_cell(ground: np.ndarray) -> tuple[int, int]:
    """The square metre deepest inside the open yard: erode until one more step would empty it."""
    if not ground.any():
        raise ValueError("open_yard_cell: the mask has no ground")
    # a one-cell border of not-yard, so the array edge erodes like any other boundary
    core = np.pad(ground.astype(bool), 1)
    while True:
        nxt = core.copy()
        nxt[1:] &= core[:-1]
        nxt[:-1] &= core[1:]
        nxt[:, 1:] &= core[:, :-1]
        nxt[:, :-1] &= core[:, 1:]
        if not nxt.any():
            break
        core = nxt
    rows, cols = np.nonzero(core)
    k = int(np.argmin((rows - rows.mean()) ** 2 + (cols - cols.mean()) ** 2))
    return int(rows[k]) - 1, int(cols[k]) - 1


def run_sun(hour: MetHour, site: Site) -> dict[str, Any]:
    """The sun SOLWEIG used for this hour, and the point on Earth it stood over at that instant."""
    at = hour.time - timedelta(minutes=30)
    sun = hour.sun(site)
    if sun != sun_position(at, site.latitude, site.longitude, site.utc_offset):
        raise RuntimeError("MetHour.sun no longer takes the sun at mid-hour; fix `at` here")
    lat, lon = subsolar_point(at - timedelta(hours=site.utc_offset))
    return {
        "hour": hour.label,
        "at": at.strftime("%H:%M"),
        "subsolar": [round(lat, 2), round(lon, 2)],
        "site": [round(site.latitude, 4), round(site.longitude, 4)],
        "altitude": round(sun.altitude, 1),
    }


def export_showcase(day: str, out: Path) -> None:
    """The numbers the home page tells its story with, each read off a stored run."""
    from neem_core.scene import Scene

    base = lake.run_dir(SHOWCASE, f"{day}-base")
    meta = json.loads((base / "meta.json").read_text())
    hours = [MetHour(**(h | {"time": datetime.fromisoformat(h["time"])})) for h in meta["hours"]]
    hour = next(h for h in hours if h.label == "13:00")

    scene = Scene.load(lake.scene_dir(SHOWCASE))
    ground = scene.zones == ZONE_GROUND
    utci = field_at(base, "13:00")
    tmrt = field_at(base, "13:00", "tmrt")
    r, c = open_yard_cell(ground)
    today = json.loads((base / "child.json").read_text())["morning"]
    yard_today = round(float(np.nanmean(utci[ground])), 2)

    # plan numbers come from the run that drew the plan image, not from the agent's notes
    stored = json.loads((lake.ROOT / "plans" / f"{SHOWCASE}.json").read_text())
    if stored["day"] != day:
        raise ValueError(f"plans/{SHOWCASE}.json was made for {stored['day']}, not {day}")
    plan = json.loads((lake.run_dir(SHOWCASE, f"{day}-plan") / "meta.json").read_text())
    k = plan["hours"].index("13:00")
    rows, cols = scene.zones.shape
    showcase = {
        "school_id": SHOWCASE,
        "name": meta["name"],
        "day": day,
        "sun": run_sun(hour, Site(**meta["site"])),
        "grid": {"rows": rows, "cols": cols},
        "cell": {
            "row": r,
            "col": c,
            "utci": round(float(utci[r, c]), 1),
            "tmrt": round(float(tmrt[r, c]), 1),
            "ta": hour.ta,
            "rh": hour.rh,
            "ws": hour.ws,
        },
        "plan": {
            "trees": plan["trees"],
            "cost_rs": plan["cost_rs"],
            "budget_rs": stored["budget_rs"],
            "yard_1pm": [yard_today, plan["utci_ground_by_hour"][k]],
            "child_rise": [today["peak_rise"], plan["child"]["peak_rise"]],
            "water_ml": [today["total_water_ml"], plan["child"]["total_water_ml"]],
        },
    }
    out.write_text(json.dumps(showcase))


def export_twin(school_id: str, day: str, out: Path) -> None:
    """Everything the browser planner needs, as static files: no server for the preview."""
    from neem_api import read_model

    out.mkdir(parents=True, exist_ok=True)
    payload, ref = read_model.layers_bin(school_id, day)
    # int16 heat fields compress about 3x; the browser inflates them with DecompressionStream.
    # mtime=0 keeps the file byte-identical across publishes of the same run.
    (out / "layers.bin.gz").write_bytes(gzip.compress(payload, 9, mtime=0))
    (out / "layers.bin").unlink(missing_ok=True)
    heat_png(school_id, f"{day}-base", out / "map-1pm.png")
    if (lake.run_dir(school_id, f"{day}-plan") / "field.npz").exists():
        heat_png(school_id, f"{day}-plan", out / "map-1pm-plan.png")
    summary = read_model.twin_summary(school_id, day) | {"height_ref": ref}
    (out / "twin.json").write_text(json.dumps(summary))
    (out / "calibration.json").write_text(json.dumps(read_model.calibration(school_id, day)))
    (out / "child.json").write_text(json.dumps(read_model.child(school_id, day)))
    plan = lake.ROOT / "plans" / f"{school_id}.json"
    if plan.exists():  # the planner agent's verified suggestion, if it has run
        (out / "plan.json").write_text(plan.read_text())


def publish(day: str, web: Path) -> None:
    data = web / "src" / "data"
    thumbs = web / "public" / "thumbs"
    data.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)

    from neem_api.read_model import has_twin, ranking

    df = ranking(day).sort_values(by=["utci_mean"], ascending=[False]).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    keep = [
        "rank",
        "school_id",
        "name",
        "government",
        "area_m2",
        "utci_mean",
        "utci_peak_hour_mean",
        "extreme_fraction",
        "shade_fraction",
        "canopy_cover",
        "height_coverage",
        "lat",
        "lon",
    ]
    table = pd.DataFrame(df.loc[:, keep]).round(4)
    rows: list[dict[str, Any]] = [
        {str(k): v for k, v in rec.items()} for rec in table.to_dict(orient="records")
    ]
    for r in rows:
        r["has_twin"] = has_twin(str(r["school_id"]), day)
        src = lake.path("rank", day, "maps", f"{r['school_id']}.npz")
        if src.exists():
            thumbnail(src, thumbs / f"{r['school_id']}.png")

    canopy = df["canopy_cover"].to_numpy(dtype=float)
    heat = df["utci_mean"].to_numpy(dtype=float)
    extreme = df["extreme_fraction"].to_numpy(dtype=float)
    status = pd.read_parquet(lake.path("rank", day, "schools.parquet"))["status"].to_numpy()
    stats = {
        "day": day,
        "schools": len(df),
        "government": int(df["government"].to_numpy(dtype=bool).sum()),
        "canopy_heat_r": round(float(np.corrcoef(canopy, heat)[0, 1]), 3),
        "utci_min": round(float(heat.min()), 1),
        "utci_median": round(float(np.median(heat)), 1),
        "utci_max": round(float(heat.max()), 1),
        "share_quarter_extreme": round(float((extreme > 0.25).mean()), 3),
        "failed_no_ground": int((status != "ok").sum()),
    }
    (data / "ranking.json").write_text(json.dumps({"stats": stats, "schools": rows}))
    (data / "palette.json").write_text(json.dumps(to_json()))
    twins = [r for r in rows if r["has_twin"]]
    (data / "twins.json").write_text(json.dumps(twins))
    for t in twins:
        export_twin(str(t["school_id"]), day, web / "public" / "twins" / str(t["school_id"]))
    export_showcase(day, data / "showcase.json")
    print(f"publish: {len(rows)} schools, {len(twins)} twins, r={stats['canopy_heat_r']} -> {web}")
