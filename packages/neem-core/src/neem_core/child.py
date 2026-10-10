"""Child body twin: JOS-3 multi-node thermoregulation, scaled to a child.

JOS-3 is validated on adults. Scaling height and weight changes body surface area and mass,
the first-order reasons children heat faster, but the model's set points do not scale: a
child-sized body rests at about 38.0 C core where an adult rests at 36.9 C. So we report the
rise in core temperature above the child's own resting state, which is what heat-strain
studies compare, and never the raw absolute value. Lower sweat rates in children are not
captured; results are indicative and labelled as such.
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

RESTING_CORE = 37.0  # typical resting core for display: shown = RESTING_CORE + rise
STRAIN_RISE = 1.0  # a 1 C rise (about 38 C core) is the usual heat-strain line


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
    rise: np.ndarray  # core temperature above the child's resting state, C
    skin: np.ndarray  # mean skin temperature, C
    water_ml: np.ndarray  # cumulative water lost to sweat and breath, ml
    labels: list[str]  # activity label per minute

    @property
    def peak_rise(self) -> float:
        return float(self.rise.max())

    @property
    def total_water_ml(self) -> float:
        return float(self.water_ml[-1])

    def minutes_strained(self, rise: float = STRAIN_RISE) -> int:
        return int((self.rise > rise).sum())

    def to_json(self) -> dict:
        return {
            "minutes": self.minutes.tolist(),
            "rise": self.rise.round(3).tolist(),
            "core_display": (RESTING_CORE + self.rise).round(2).tolist(),
            "skin": self.skin.round(3).tolist(),
            "water_ml": self.water_ml.round(1).tolist(),
            "labels": self.labels,
            "peak_rise": round(self.peak_rise, 2),
            "total_water_ml": round(self.total_water_ml),
            "minutes_strained": self.minutes_strained(),
        }


def simulate(activities: Sequence[Activity], child: Child | None = None) -> ChildDay:
    """Run the schedule minute by minute, carrying body state across activities."""
    child = child or Child()
    body = JOS3(
        height=child.height, weight=child.weight, fat=child.fat, age=child.age, sex=child.sex
    )
    # Settle in a thermally neutral room; that state is the zero for `rise`.
    body.tdb, body.tr, body.rh, body.v, body.par, body.clo = 28.0, 28.0, 50.0, 0.2, 1.2, 0.5
    body.simulate(times=60, dtime=60, output=False)
    resting = float(np.asarray(body.t_cb).ravel()[0])

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
    return ChildDay(
        minutes=np.arange(n), rise=core - resting, skin=skin, water_ml=water, labels=labels
    )
