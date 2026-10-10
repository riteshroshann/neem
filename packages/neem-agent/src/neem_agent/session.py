"""The working design for one school, and the cheap and expensive ways to evaluate it."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from typing import Any

import numpy as np

from neem_agent.sites import hottest_sites
from neem_core.engine import HeatField
from neem_core.interventions import SPECIES, Intervention, ShadeSail, Tree, apply, total_cost
from neem_core.scene import ZONE_GROUND, Scene
from neem_core.surrogate import Calibration, HourModel, predict
from neem_data import lake
from neem_data.designs import verify
from neem_data.forcing import met_hours

# Outdoor moments on the morning shift: assembly, recess, walk home (labels are hour ends).
CHILD_HOURS = ("08:00", "11:00", "13:00")


@dataclass
class Twin:
    school_id: str
    day: str
    scene: Scene
    base: HeatField
    cal: Calibration

    def hour_index(self, label: str) -> int:
        return [h.label for h in self.base.hours].index(label)

    def base_ground_utci(self, k: int) -> float:
        return float(np.nanmean(self.base.utci[k][self.scene.mask(ZONE_GROUND)]))

    def child_heat(self) -> np.ndarray:
        """Mean UTCI over the hours children are outside, per cell."""
        idx = [self.hour_index(h) for h in CHILD_HOURS]
        return self.base.utci[idx].mean(axis=0)


@cache
def load(school_id: str, day: str) -> Twin:
    run = lake.run_dir(school_id, f"{day}-base")
    scene = Scene.load(lake.scene_dir(school_id))
    with np.load(run / "field.npz") as f:
        stamps = [datetime.fromisoformat(str(t)) for t in f["hours"]]
        hours = [h for h in met_hours(day) if h.time in stamps]
        base = HeatField(
            hours=hours,
            tmrt=f["tmrt"].astype(np.float32),
            utci=f["utci"].astype(np.float32),
            sunlit=f["sunlit"].astype(np.float32),
            svf=f["svf"].astype(np.float32),
        )
    raw = json.loads((run / "calibration.json").read_text())
    cal = Calibration(
        school_id=school_id,
        hours=[
            HourModel(
                label=h["label"],
                altitude=h["altitude"],
                azimuth=h["azimuth"],
                coef=tuple(h["coef"]),
                lut_tmrt=h["lut_tmrt"],
                lut_utci=h["lut_utci"],
                mae_changed=h["mae_changed"],
            )
            for h in raw["hours"]
        ],
    )
    return Twin(school_id, day, scene, base, cal)


@dataclass
class Session:
    twin: Twin
    design: list[Intervention] = field(default_factory=list)
    verified: dict[str, Any] | None = None
    log: list[str] = field(default_factory=list)

    @property
    def cost(self) -> int:
        return total_cost(self.design)

    def trees(self) -> list[Tree]:
        return [d for d in self.design if isinstance(d, Tree)]

    def place_trees(self, count: int, species: str) -> list[Tree]:
        """Replace the trees with `count` new ones on the hottest open spots; sails stay."""
        sp = species if species in SPECIES else "neem"
        _, radius, _ = SPECIES[sp]
        sails = [d for d in self.design if isinstance(d, ShadeSail)]
        taken = [(s.x, s.y, max(s.width, s.depth) / 2 + radius) for s in sails]
        sites = hottest_sites(self.twin.scene, self.twin.child_heat(), count, 2 * radius, taken)
        trees = [Tree(x, y, sp) for x, y in sites]  # type: ignore[arg-type]
        self.design = sails + list(trees)
        self.verified = None
        return trees

    def add_sail(self, width: float, depth: float) -> ShadeSail | None:
        taken = [(t.x, t.y, t.radius + max(width, depth) / 2) for t in self.trees()]
        sites = hottest_sites(self.twin.scene, self.twin.child_heat(), 1, 0.0, taken)
        if not sites:
            return None
        sail = ShadeSail(sites[0][0], sites[0][1], width, depth)
        self.design.append(sail)
        self.verified = None
        return sail

    def preview(self) -> dict[str, Any]:
        """T0 estimate over the morning shift, anchored on the base SOLWEIG run."""
        t = self.twin
        edited = apply(t.scene, self.design)
        _, utci = predict(t.cal, edited, t.scene, t.base)
        ground = t.scene.mask(ZONE_GROUND)
        out = {}
        for label in CHILD_HOURS:
            k = t.hour_index(label)
            out[label] = {
                "today": round(float(np.nanmean(t.base.utci[k][ground])), 2),
                "plan": round(float(np.nanmean(utci[k][ground])), 2),
            }
        return {
            "hours": out,
            "cost_rs": self.cost,
            "trees": len(self.trees()),
            "sails": len(self.design) - len(self.trees()),
        }

    def verify(self) -> dict[str, Any]:
        self.verified = verify(self.twin.school_id, self.twin.day, self.design)
        return self.verified

    def design_json(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "trees": [{"x": d.x, "y": d.y, "species": d.species} for d in self.trees()],
            "sails": [
                {"x": d.x, "y": d.y, "width": d.width, "depth": d.depth}
                for d in self.design
                if isinstance(d, ShadeSail)
            ],
        }
