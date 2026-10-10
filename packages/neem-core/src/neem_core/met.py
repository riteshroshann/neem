"""Meteorological forcing shared by every tier."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from neem_core.sun import SunPosition, sun_position


@dataclass(frozen=True, slots=True)
class Site:
    latitude: float
    longitude: float
    altitude: float
    utc_offset: float


@dataclass(frozen=True, slots=True)
class MetHour:
    """One hour of forcing. Radiation is the mean over the hour ending at `time`."""

    time: datetime  # local clock time, end of the averaging hour
    ta: float  # C
    rh: float  # %
    global_rad: float  # W/m2
    direct_rad: float  # W/m2, normal incidence
    diffuse_rad: float  # W/m2, horizontal
    ws: float  # m/s at 10 m
    pressure: float = 1013.25  # hPa

    def sun(self, site: Site) -> SunPosition:
        # Radiation is an hourly mean, so the sun is taken at the middle of the hour.
        mid = self.time - timedelta(minutes=30)
        return sun_position(mid, site.latitude, site.longitude, site.utc_offset)

    @property
    def label(self) -> str:
        return self.time.strftime("%H:%M")
