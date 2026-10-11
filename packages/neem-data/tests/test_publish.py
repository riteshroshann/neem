import math
from datetime import datetime

import numpy as np
import pytest

from neem_core.met import MetHour, Site
from neem_data.publish import open_yard_cell, run_sun


def is_interior(ground: np.ndarray, r: int, c: int) -> bool:
    rows, cols = ground.shape
    if not (0 < r < rows - 1 and 0 < c < cols - 1):
        return False
    return bool(ground[r - 1 : r + 2, c].all() and ground[r, c - 1 : c + 2].all())


def test_yard_on_the_array_edge_gives_an_interior_cell():
    ground = np.zeros((10, 8), dtype=bool)
    ground[2:8, 0:3] = True  # 6 x 3 yard against the west edge
    r, c = open_yard_cell(ground)
    assert c == 1
    assert is_interior(ground, r, c)


@pytest.mark.timeout(10)
def test_all_ground_terminates_at_the_centre():
    assert open_yard_cell(np.ones((9, 7), dtype=bool)) == (4, 3)


def test_no_ground_raises():
    with pytest.raises(ValueError, match="no ground"):
        open_yard_cell(np.zeros((4, 4), dtype=bool))


def test_showcase_sun_is_the_one_solweig_used():
    # Kendriya Vidyalaya, Rohini, at 1 pm on the showcase day
    site = Site(latitude=28.7355, longitude=77.0925, altitude=215.6, utc_offset=5.5)
    hour = MetHour(datetime(2026, 4, 27, 13), 42.1, 14, 870, 669.7, 233, 3.58, 977.5)
    sun = run_sun(hour, site)
    assert (sun["hour"], sun["at"]) == ("13:00", "12:30")
    assert sun["altitude"] == round(hour.sun(site).altitude, 1)
    # the zenith angle at the site is its arc to the subsolar point, so both are one instant
    lat1, lon1 = (math.radians(v) for v in sun["site"])
    lat2, lon2 = (math.radians(v) for v in sun["subsolar"])
    cos_arc = math.sin(lat1) * math.sin(lat2)
    cos_arc += math.cos(lat1) * math.cos(lat2) * math.cos(lon1 - lon2)
    arc = math.acos(cos_arc)
    assert math.degrees(arc) == pytest.approx(90 - sun["altitude"], abs=0.1)
