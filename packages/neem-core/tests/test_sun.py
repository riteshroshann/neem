from datetime import datetime, timedelta

import pytest

from neem_core.sun import subsolar_point, sun_position

DELHI = (28.6139, 77.2090, 5.5)


def _noon_altitude(day: datetime) -> float:
    times = [day + timedelta(minutes=m) for m in range(10 * 60, 15 * 60)]
    return max(sun_position(t, *DELHI).altitude for t in times)


def test_summer_solstice_noon_altitude_matches_geometry() -> None:
    # 90 - (latitude - declination) with declination 23.44 on the solstice
    assert _noon_altitude(datetime(2026, 6, 21)) == pytest.approx(84.83, abs=0.3)


def test_equinox_noon_altitude_matches_geometry() -> None:
    assert _noon_altitude(datetime(2026, 3, 20)) == pytest.approx(90 - 28.6139, abs=0.6)


def test_morning_sun_is_in_the_east_and_evening_in_the_west() -> None:
    morning = sun_position(datetime(2026, 6, 29, 8, 0), *DELHI)
    evening = sun_position(datetime(2026, 6, 29, 17, 0), *DELHI)
    assert 60 < morning.azimuth < 110
    assert 250 < evening.azimuth < 300


def test_night_is_below_horizon() -> None:
    assert sun_position(datetime(2026, 6, 29, 23, 0), *DELHI).altitude < 0


@pytest.mark.parametrize("hour", [0, 7, 12, 19])
def test_sun_is_overhead_at_the_subsolar_point(hour: int) -> None:
    utc = datetime(2026, 4, 27, hour, 30)
    lat, lon = subsolar_point(utc)
    assert sun_position(utc, lat, lon, 0.0).altitude == pytest.approx(90.0, abs=0.05)
