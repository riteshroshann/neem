"""Solar position from the NOAA spreadsheet algorithm (accurate to about 0.01 degrees)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class SunPosition:
    altitude: float  # degrees above the horizon
    azimuth: float  # degrees clockwise from north


def sun_position(
    when: datetime, latitude: float, longitude: float, utc_offset: float
) -> SunPosition:
    """Sun position at a local clock time. `when` is naive local time."""
    utc = when - timedelta(hours=utc_offset)
    jd = _julian_day(utc)
    jc = (jd - 2451545.0) / 36525.0

    geom_mean_long = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    geom_mean_anom = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    m = math.radians(geom_mean_anom)
    eq_ctr = (
        math.sin(m) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + math.sin(2 * m) * (0.019993 - 0.000101 * jc)
        + math.sin(3 * m) * 0.000289
    )
    true_long = geom_mean_long + eq_ctr
    omega = math.radians(125.04 - 1934.136 * jc)
    app_long = true_long - 0.00569 - 0.00478 * math.sin(omega)
    mean_obliq = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    obliq = math.radians(mean_obliq + 0.00256 * math.cos(omega))
    decl = math.asin(math.sin(obliq) * math.sin(math.radians(app_long)))

    y = math.tan(obliq / 2) ** 2
    l0 = math.radians(geom_mean_long)
    eq_time = 4 * math.degrees(
        y * math.sin(2 * l0)
        - 2 * ecc * math.sin(m)
        + 4 * ecc * y * math.sin(m) * math.cos(2 * l0)
        - 0.5 * y * y * math.sin(4 * l0)
        - 1.25 * ecc * ecc * math.sin(2 * m)
    )

    minutes = utc.hour * 60 + utc.minute + utc.second / 60
    true_solar = (minutes + eq_time + 4 * longitude) % 1440
    hour_angle = true_solar / 4 - 180 if true_solar >= 0 else true_solar / 4 + 180

    lat = math.radians(latitude)
    ha = math.radians(hour_angle)
    cos_zen = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    zen = math.acos(max(-1.0, min(1.0, cos_zen)))

    sin_zen = math.sin(zen)
    if sin_zen < 1e-9:
        azimuth = 180.0
    else:
        cos_az = (math.sin(lat) * math.cos(zen) - math.sin(decl)) / (math.cos(lat) * sin_zen)
        az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
        azimuth = (az + 180) % 360 if hour_angle > 0 else (540 - az) % 360

    return SunPosition(altitude=90.0 - math.degrees(zen), azimuth=azimuth)


def _julian_day(utc: datetime) -> float:
    y, mo = utc.year, utc.month
    if mo <= 2:
        y -= 1
        mo += 12
    a = y // 100
    b = 2 - a + a // 4
    day = utc.day + (utc.hour + utc.minute / 60 + utc.second / 3600) / 24
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (mo + 1)) + day + b - 1524.5
