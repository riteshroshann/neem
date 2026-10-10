"""T0: shadow casting plus a per-hour linear map to Tmrt, calibrated against SOLWEIG (ADR 0002).

    Tmrt ≈ a + b·sunlit + c·svf + d·under_canopy

sunlit comes from our own shadow caster on the edited surface, svf from the base SOLWEIG run,
under_canopy from the edited canopy. UTCI is then a monotone per-hour lookup from Tmrt, read off
SOLWEIG's own (Tmrt, UTCI) pairs, because air temperature, humidity and wind are uniform.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from neem_core.engine import HeatField
from neem_core.met import MetHour, Site
from neem_core.scene import ZONE_BUILDING, Scene
from neem_core.shadow import sunlit_fraction

LUT_STEP = 0.5  # C of Tmrt between lookup points


@dataclass(slots=True)
class HourModel:
    label: str
    altitude: float
    azimuth: float
    coef: tuple[float, float, float, float]  # a, b, c, d
    lut_tmrt: list[float]
    lut_utci: list[float]
    mae: float  # Tmrt MAE on held-out cells, C


@dataclass(slots=True)
class Calibration:
    school_id: str
    hours: list[HourModel]

    def to_json(self) -> dict:
        return {
            "school_id": self.school_id,
            "hours": [
                {
                    "label": h.label,
                    "altitude": round(h.altitude, 4),
                    "azimuth": round(h.azimuth, 4),
                    "coef": [round(c, 5) for c in h.coef],
                    "lut_tmrt": h.lut_tmrt,
                    "lut_utci": [round(u, 3) for u in h.lut_utci],
                    "mae": round(h.mae, 3),
                }
                for h in self.hours
            ],
        }


def features(scene: Scene, svf: np.ndarray, altitude: float, azimuth: float) -> np.ndarray:
    """(rows, cols, 4) design matrix: 1, sunlit, svf, under_canopy."""
    lit = sunlit_fraction(
        scene.dsm, scene.dem, scene.cdsm, scene.grid.pixel_size, altitude, azimuth
    )
    under = (scene.cdsm > 0).astype(np.float32)
    return np.stack([np.ones_like(lit), lit, svf, under], axis=-1)


def _lut(tmrt: np.ndarray, utci: np.ndarray) -> tuple[list[float], list[float]]:
    lo = float(np.floor(np.nanmin(tmrt) / LUT_STEP) * LUT_STEP) - 5
    hi = float(np.ceil(np.nanmax(tmrt) / LUT_STEP) * LUT_STEP) + 5
    grid = np.arange(lo, hi + LUT_STEP, LUT_STEP)
    order = np.argsort(tmrt)
    t, u = tmrt[order], utci[order]
    # A least-squares line per hour is enough: UTCI is near-linear in Tmrt over this range.
    slope, intercept = np.polyfit(t, u, 1)
    knots = np.interp(grid, t, u, left=np.nan, right=np.nan)
    knots = np.where(np.isnan(knots), slope * grid + intercept, knots)
    return grid.round(2).tolist(), np.maximum.accumulate(knots).tolist()


def fit(
    scenes: Sequence[Scene],
    fields: Sequence[HeatField],
    site: Site,
    holdout: float = 0.2,
    seed: int = 0,
) -> Calibration:
    """Fit one HourModel per hour on all non-roof cells of every (scene, field) pair.

    svf always comes from the first field (the base scene), as it would in the browser.
    """
    base_svf = fields[0].svf
    rng = np.random.default_rng(seed)
    models: list[HourModel] = []
    for k, hour in enumerate(fields[0].hours):
        sun = hour.sun(site)
        xs, ys, tm, ut = [], [], [], []
        for scene, field in zip(scenes, fields, strict=True):
            keep = (scene.zones != ZONE_BUILDING) & np.isfinite(field.tmrt[k])
            x = features(scene, base_svf, sun.altitude, sun.azimuth)[keep]
            xs.append(x)
            ys.append(field.tmrt[k][keep])
            tm.append(field.tmrt[k][keep])
            ut.append(field.utci[k][keep])
        X, y = np.concatenate(xs), np.concatenate(ys)
        test = rng.random(len(y)) < holdout
        coef, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
        mae = float(np.mean(np.abs(X[test] @ coef - y[test])))
        lut_t, lut_u = _lut(np.concatenate(tm), np.concatenate(ut))
        models.append(
            HourModel(
                label=hour.label,
                altitude=sun.altitude,
                azimuth=sun.azimuth,
                coef=(float(coef[0]), float(coef[1]), float(coef[2]), float(coef[3])),
                lut_tmrt=lut_t,
                lut_utci=lut_u,
                mae=mae,
            )
        )
    return Calibration(school_id=scenes[0].school_id, hours=models)


def predict(cal: Calibration, scene: Scene, svf: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """T0 Tmrt and UTCI for an edited scene, (hours, rows, cols) each."""
    tmrt, utci = [], []
    for h in cal.hours:
        x = features(scene, svf, h.altitude, h.azimuth)
        t = x @ np.asarray(h.coef, dtype=np.float32)
        tmrt.append(t)
        utci.append(np.interp(t, h.lut_tmrt, h.lut_utci))
    return np.stack(tmrt).astype(np.float32), np.stack(utci).astype(np.float32)


def school_hours(hours: Sequence[MetHour], start: int = 8, end: int = 14) -> list[MetHour]:
    return [h for h in hours if start <= h.time.hour <= end]
