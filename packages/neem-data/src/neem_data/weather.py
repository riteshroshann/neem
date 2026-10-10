"""Hourly weather forcing for a day, from ERA5 via Open-Meteo's archive API."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from neem_data.aoi import DELHI_LATLON
from neem_data.http import get_json
from neem_data.sources import OPEN_METEO_ARCHIVE


@dataclass(frozen=True, slots=True)
class HourlyMet:
    time: str  # local ISO timestamp, start of the hour
    ta: float  # air temperature, C
    rh: float  # relative humidity, %
    global_rad: float  # global horizontal irradiance, W/m2 (hour mean)
    direct_rad: float  # direct normal irradiance, W/m2
    diffuse_rad: float  # diffuse horizontal irradiance, W/m2
    ws: float  # wind speed at 10 m, m/s
    pressure: float  # surface pressure, hPa

    @property
    def datetime(self) -> datetime:
        return datetime.fromisoformat(self.time)


def fetch_day(day: date, out: Path, latlon: tuple[float, float] = DELHI_LATLON) -> list[HourlyMet]:
    params = {
        "latitude": latlon[0],
        "longitude": latlon[1],
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "shortwave_radiation",
                "direct_normal_irradiance",
                "diffuse_radiation",
                "wind_speed_10m",
                "surface_pressure",
            ]
        ),
        "wind_speed_unit": "ms",
        "timezone": "Asia/Kolkata",
    }
    h = get_json(OPEN_METEO_ARCHIVE, params=params)["hourly"]
    hours = [
        HourlyMet(
            time=h["time"][i],
            ta=float(h["temperature_2m"][i]),
            rh=float(h["relative_humidity_2m"][i]),
            global_rad=float(h["shortwave_radiation"][i]),
            direct_rad=float(h["direct_normal_irradiance"][i]),
            diffuse_rad=float(h["diffuse_radiation"][i]),
            ws=float(h["wind_speed_10m"][i]),
            pressure=float(h["surface_pressure"][i]),
        )
        for i in range(len(h["time"]))
    ]
    out.write_text(json.dumps([asdict(x) for x in hours], indent=1))
    peak = max(hours, key=lambda x: x.ta)
    print(f"met: {day} peak {peak.ta:.1f} C at {peak.time[11:16]} -> {out}")
    return hours


def fetch_range_daily_max(
    start: date, end: date, latlon: tuple[float, float] = DELHI_LATLON
) -> dict[date, float]:
    params = {
        "latitude": latlon[0],
        "longitude": latlon[1],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max",
        "timezone": "Asia/Kolkata",
    }
    d = get_json(OPEN_METEO_ARCHIVE, params=params)["daily"]
    return {
        date.fromisoformat(t): float(v)
        for t, v in zip(d["time"], d["temperature_2m_max"], strict=True)
        if v is not None
    }


def load_day(path: Path) -> list[HourlyMet]:
    return [HourlyMet(**x) for x in json.loads(path.read_text())]
