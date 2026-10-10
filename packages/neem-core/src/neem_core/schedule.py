"""A school day as the child twin sees it: where the child is, doing what, in which heat."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal

import numpy as np

from neem_core.child import PAR_PLAY, PAR_SEATED, PAR_STANDING, PAR_WALKING, Activity
from neem_core.met import MetHour

Place = Literal["ground", "classroom", "path"]

# Wind at child height from 10 m wind, log profile over rough urban ground.
WIND_AT_1M = 0.4


@dataclass(frozen=True, slots=True)
class Slot:
    label: str
    start: time
    minutes: int
    place: Place
    par: float


# Delhi government school, summer morning shift (7:30 to 12:30)
MORNING_SHIFT = (
    Slot("Assembly", time(7, 30), 20, "ground", PAR_STANDING),
    Slot("Class", time(7, 50), 130, "classroom", PAR_SEATED),
    Slot("Recess", time(10, 0), 30, "ground", PAR_PLAY),
    Slot("Class", time(10, 30), 120, "classroom", PAR_SEATED),
    Slot("Walk home", time(12, 30), 15, "path", PAR_WALKING),
)

# Afternoon shift scenario, for schools that run two shifts
AFTERNOON_SHIFT = (
    Slot("Assembly", time(13, 0), 15, "ground", PAR_STANDING),
    Slot("Class", time(13, 15), 135, "classroom", PAR_SEATED),
    Slot("Recess", time(15, 30), 30, "ground", PAR_PLAY),
    Slot("Class", time(16, 0), 110, "classroom", PAR_SEATED),
    Slot("Walk home", time(17, 50), 15, "path", PAR_WALKING),
)


def hour_index(hours: Sequence[MetHour], at: datetime) -> int:
    """Index of the forcing hour whose averaging window contains `at`."""
    ends = [h.time for h in hours]
    for i, end in enumerate(ends):
        if end - timedelta(hours=1) <= at < end:
            return i
    return int(np.argmin([abs((e - at).total_seconds()) for e in ends]))


def build_day(
    slots: Sequence[Slot],
    hours: Sequence[MetHour],
    outdoor_tmrt: Sequence[float],
) -> list[Activity]:
    """Activities for the twin. `outdoor_tmrt[i]` is the Tmrt where the child stands at hour i.

    Classrooms are not modelled (a non-goal); they are taken as 1.5 C below outdoor air with
    walls at air temperature, a fan-ventilated room with no direct sun.
    """
    day = hours[0].time.date()
    activities = []
    for s in slots:
        mid = datetime.combine(day, s.start) + timedelta(minutes=s.minutes / 2)
        k = hour_index(hours, mid)
        h = hours[k]
        if s.place == "classroom":
            ta = h.ta - 1.5
            activities.append(Activity(s.label, s.minutes, ta, ta, h.rh, 0.6, s.par))
        else:
            v = max(0.3, h.ws * WIND_AT_1M)
            activities.append(
                Activity(s.label, s.minutes, h.ta, float(outdoor_tmrt[k]), h.rh, v, s.par)
            )
    return activities
