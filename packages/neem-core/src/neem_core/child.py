"""Child body twin: JOS-3 multi-node thermoregulation, scaled to a child.

JOS-3 is validated on adults. Scaling height, weight and age changes body surface area, mass
and basal metabolism, which captures the first-order reasons children heat faster; it does not
capture children's lower sweat rates. Results are indicative and labelled as such in the UI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from pythermalcomfort.models import JOS3

# Physical activity ratio (multiple of basal metabolism)
PAR_SEATED = 1.2
PAR_STANDING = 1.4
PAR_WALKING = 2.2
PAR_PLAY = 3.0


@dataclass(frozen=True, slots=True)
class Child:
    height: float = 1.32  # m, typical 9-year-old
    weight: float = 28.0  # kg
    age: int = 9
    sex: str = "female"
    fat: float = 20.0  # %


@dataclass(frozen=True, slots=True)
class Activity:
    label: str
    minutes: int
    ta: float  # air temperature, C
    tr: float  # mean radiant temperature, C
    rh: float  # %
    v: float  # air speed at the body, m/s
    par: float
    clo: float = 0.5  # summer school uniform


@dataclass(slots=True)
class ChildDay:
    minutes: np.ndarray  # minute index from the start of the day
    core: np.ndarray  # core (central blood) temperature, C
    skin: np.ndarray  # mean skin temperature, C
    water_ml: np.ndarray  # cumulative water lost to sweat and breath, ml
    labels: list[str]  # activity label per minute

    @property
    def peak_core(self) -> float:
        return float(self.core.max())

    @property
    def total_water_ml(self) -> float:
        return float(self.water_ml[-1])

    def minutes_above(self, threshold: float = 38.0) -> int:
        return int((self.core > threshold).sum())

    def to_json(self) -> dict:
        return {
            "minutes": self.minutes.tolist(),
            "core": self.core.round(3).tolist(),
            "skin": self.skin.round(3).tolist(),
            "water_ml": self.water_ml.round(1).tolist(),
            "labels": self.labels,
            "peak_core": round(self.peak_core, 2),
            "total_water_ml": round(self.total_water_ml),
            "minutes_above_38": self.minutes_above(38.0),
        }


def simulate(activities: Sequence[Activity], child: Child | None = None) -> ChildDay:
    """Run the schedule minute by minute, carrying body state across activities."""
    child = child or Child()
    body = JOS3(
        height=child.height, weight=child.weight, fat=child.fat, age=child.age, sex=child.sex
    )
    # Settle at classroom conditions so the day starts from a realistic state.
    body.tdb, body.tr, body.rh, body.v, body.par, body.clo = 31.0, 31.0, 50.0, 0.3, 1.2, 0.5
    body.simulate(times=30, dtime=60, output=False)

    labels: list[str] = []
    for a in activities:
        body.tdb, body.tr, body.rh, body.v, body.par, body.clo = (
            a.ta,
            a.tr,
            a.rh,
            a.v,
            a.par,
            a.clo,
        )
        body.simulate(times=a.minutes, dtime=60)
        labels.extend([a.label] * a.minutes)

    r = body.dict_results()
    if r is None:
        raise RuntimeError("JOS-3 produced no results")
    n = len(labels)
    core = np.asarray(r["t_cb"], dtype=float)[-n:]
    skin = np.asarray(r["t_skin_mean"], dtype=float)[-n:]
    loss_g_per_s = np.asarray(r["weight_loss_by_evap_and_res"], dtype=float)[-n:]
    water = np.cumsum(loss_g_per_s * 60.0)  # 1 g of water is 1 ml
    return ChildDay(minutes=np.arange(n), core=core, skin=skin, water_ml=water, labels=labels)
