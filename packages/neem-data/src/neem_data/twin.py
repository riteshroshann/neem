"""The full T1 twin for one school: base run, calibration, exposure and the child's day."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from neem_core.child import simulate
from neem_core.engine import HeatField, SolweigEngine
from neem_core.exposure import exposure
from neem_core.interventions import Tree, apply
from neem_core.scene import ZONE_BUILDING, ZONE_GROUND, Scene
from neem_core.schedule import AFTERNOON_SHIFT, MORNING_SHIFT, build_day
from neem_core.surrogate import fit
from neem_data import lake
from neem_data.forcing import met_hours, site_for
from neem_data.scene_builder import build_scene

DAY_HOURS = (7, 18)
SCHOOL_HOURS = (8, 13)


def engine() -> SolweigEngine:
    return SolweigEngine(lake.ROOT / "cache" / "solweig")


def calibration_design(scene: Scene, n: int = 14, seed: int = 7) -> list[Tree]:
    """Trees scattered over open ground so the calibration sees canopy where there is none."""
    rng = np.random.default_rng(seed)
    rows, cols = np.nonzero(scene.zones == ZONE_GROUND)
    if len(rows) == 0:
        rows, cols = np.nonzero(scene.zones != ZONE_BUILDING)
    pick = rng.choice(len(rows), min(n, len(rows)), replace=False)
    return [Tree(*scene.grid.to_map(float(rows[i]) + 0.5, float(cols[i]) + 0.5)) for i in pick]


def ground_tmrt(scene: Scene, field: HeatField) -> list[float]:
    ground = scene.mask(ZONE_GROUND)
    # the mean, not the median: it is the expected exposure of a child anywhere in the yard,
    # and it moves in proportion to the shade a design adds
    return [float(np.nanmean(field.tmrt[k][ground])) for k in range(len(field.hours))]


def save_field(path: Path, field: HeatField) -> None:
    np.savez_compressed(
        path,
        tmrt=field.tmrt.astype(np.float16),
        utci=field.utci.astype(np.float16),
        sunlit=field.sunlit.astype(np.float16),
        svf=field.svf.astype(np.float16),
        hours=np.array([h.time.isoformat() for h in field.hours]),
    )


def run_twin(school_id: str, day: str, pixel_size: float = 1.0) -> Path:
    started = time.perf_counter()
    scene, quality = build_scene(school_id, pixel_size)
    scene.save(lake.scene_dir(school_id))
    site = site_for(scene)
    hours = met_hours(day, *DAY_HOURS)

    eng = engine()
    base = eng.run(scene, hours, site)
    planted = apply(scene, calibration_design(scene))
    probe = eng.run(planted, hours, site)
    cal = fit(scene, base, [planted], [probe], site)

    in_school = [
        i for i, h in enumerate(hours) if SCHOOL_HOURS[0] <= h.time.hour <= SCHOOL_HOURS[1]
    ]
    exp = exposure(scene, base.tmrt[in_school], base.utci[in_school], base.sunlit[in_school])
    tmrt_ground = ground_tmrt(scene, base)
    morning = simulate(build_day(MORNING_SHIFT, hours, tmrt_ground))
    afternoon = simulate(build_day(AFTERNOON_SHIFT, hours, tmrt_ground))

    run_id = f"{day}-base"
    out = lake.run_dir(school_id, run_id)
    out.mkdir(parents=True, exist_ok=True)
    save_field(out / "field.npz", base)
    (out / "calibration.json").write_text(json.dumps(cal.to_json()))
    (out / "child.json").write_text(
        json.dumps({"morning": morning.to_json(), "afternoon": afternoon.to_json()})
    )
    meta = {
        "school_id": school_id,
        "name": scene.name,
        "day": day,
        "site": asdict(site),
        "hours": [asdict(h) | {"time": h.time.isoformat()} for h in hours],
        "exposure": exp.to_json(),
        "quality": asdict(quality) | {"height_coverage": round(quality.height_coverage, 3)},
        "calibration_mae_changed": [round(h.mae_changed, 2) for h in cal.hours],
        "timings": {
            "base": base.timings,
            "probe": probe.timings,
            "total_s": round(time.perf_counter() - started, 1),
        },
        "provenance": scene.provenance,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    return out
