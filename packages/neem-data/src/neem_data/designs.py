"""Verify a design with T1: the job the worker runs and the API can run in-process."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from neem_core.child import simulate
from neem_core.engine import HeatField
from neem_core.exposure import exposure
from neem_core.interventions import Intervention, ShadeSail, Tree, apply, total_cost
from neem_core.scene import ZONE_GROUND, Scene
from neem_core.schedule import MORNING_SHIFT, build_day
from neem_data import lake
from neem_data.forcing import met_hours, site_for
from neem_data.twin import SCHOOL_HOURS, engine, ground_tmrt, save_field

VERIFY_HOURS = (7, 13)  # the morning shift and its walk home


def parse(design: dict[str, Any]) -> list[Intervention]:
    items: list[Intervention] = [
        Tree(float(t["x"]), float(t["y"]), t.get("species", "neem"))
        for t in design.get("trees", [])
    ]
    items += [
        ShadeSail(float(s["x"]), float(s["y"]), float(s["width"]), float(s["depth"]))
        for s in design.get("sails", [])
    ]
    return items


def verify(school_id: str, day: str, interventions: Sequence[Intervention]) -> dict[str, Any]:
    """Full SOLWEIG run of the edited school, with exposure and the child's morning."""
    return _verify(school_id, day, interventions)[0]


def verify_plan(school_id: str, day: str) -> Path:
    """Re-run the planner's stored design and keep the field, so the site can draw it."""
    plan = json.loads((lake.ROOT / "plans" / f"{school_id}.json").read_text())
    result, field = _verify(school_id, day, parse(plan["design"]))
    out = lake.run_dir(school_id, f"{day}-plan")
    out.mkdir(parents=True, exist_ok=True)
    save_field(out / "field.npz", field)
    (out / "meta.json").write_text(json.dumps(result, indent=2))
    return out


def _verify(
    school_id: str, day: str, interventions: Sequence[Intervention]
) -> tuple[dict[str, Any], HeatField]:
    started = time.perf_counter()
    base = Scene.load(lake.scene_dir(school_id))
    edited = apply(base, interventions)
    hours = met_hours(day, *VERIFY_HOURS)
    field = engine().run(edited, hours, site_for(edited))
    in_school = [i for i, h in enumerate(hours) if SCHOOL_HOURS[0] <= h.time.hour]
    exp = exposure(edited, field.tmrt[in_school], field.utci[in_school], field.sunlit[in_school])
    child = simulate(build_day(MORNING_SHIFT, hours, ground_tmrt(edited, field)))
    ground = edited.mask(ZONE_GROUND)
    return {
        "school_id": school_id,
        "day": day,
        "cost_rs": total_cost(interventions),
        "trees": sum(isinstance(i, Tree) for i in interventions),
        "sails": sum(isinstance(i, ShadeSail) for i in interventions),
        "hours": [h.label for h in hours],
        "exposure": exp.to_json(),
        "child": child.to_json(),
        "utci_ground_by_hour": [round(float(np.nanmean(u[ground])), 2) for u in field.utci],
        "seconds": round(time.perf_counter() - started, 2),
        "timings": field.timings,
    }, field


def baseline(school_id: str, day: str) -> dict[str, Any]:
    meta = json.loads((lake.run_dir(school_id, f"{day}-base") / "meta.json").read_text())
    child = json.loads((lake.run_dir(school_id, f"{day}-base") / "child.json").read_text())
    return {"exposure": meta["exposure"], "child": child["morning"]}
