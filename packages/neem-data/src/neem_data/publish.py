"""Export what the static site needs: ranking, twins index, palette and heat thumbnails."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image

from neem_core.palette import colorize, to_json
from neem_core.scene import ZONE_BUILDING, ZONE_GROUND
from neem_data import lake

PAPER = (255, 255, 255)
ROOF = (214, 214, 214)
THUMB_PX = 96


def thumbnail(src: Path, dst: Path) -> None:
    with np.load(src) as z:
        utci, zones = z["utci"].astype(np.float32), z["zones"]
    rgb = colorize(utci)
    rgb[zones == ZONE_BUILDING] = ROOF
    rgb[(zones != ZONE_GROUND) & (zones != ZONE_BUILDING)] = PAPER
    rows, cols = np.nonzero(zones)
    if len(rows):  # crop to the school, keep it square
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        side = max(r1 - r0, c1 - c0)
        rc, cc = (r0 + r1) // 2, (c0 + c1) // 2
        r0, c0 = max(0, rc - side // 2), max(0, cc - side // 2)
        rgb = rgb[r0 : r0 + side, c0 : c0 + side]
    img = Image.fromarray(rgb).resize((THUMB_PX, THUMB_PX), Image.Resampling.NEAREST)
    img.save(dst, optimize=True)


def export_twin(school_id: str, day: str, out: Path) -> None:
    """Everything the browser planner needs, as static files: no server for the preview."""
    from neem_api import read_model

    out.mkdir(parents=True, exist_ok=True)
    payload, ref = read_model.layers_bin(school_id, day)
    (out / "layers.bin").write_bytes(payload)
    summary = read_model.twin_summary(school_id, day) | {"height_ref": ref}
    (out / "twin.json").write_text(json.dumps(summary))
    (out / "calibration.json").write_text(json.dumps(read_model.calibration(school_id, day)))
    (out / "child.json").write_text(json.dumps(read_model.child(school_id, day)))


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
    print(f"publish: {len(rows)} schools, {len(twins)} twins, r={stats['canopy_heat_r']} -> {web}")
