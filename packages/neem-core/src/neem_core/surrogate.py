"""T0: predict how a design changes the heat field, anchored on the base SOLWEIG run (ADR 0002).

    Tmrt_edit = Tmrt_base + (F(edit) - F(base)) · coef_h

F is cheap geometry: sunlit fraction from our shadow caster, canopy overhead, sunlit x sky
view, and canopy nearby. Cells a design does not touch keep SOLWEIG's exact value; model
error lives only where something changed. coef_h is fit per hour on the difference between
a base run and a probe run with trees scattered over the yard. UTCI moves along a per-hour
monotone lookup read off SOLWEIG's own (Tmrt, UTCI) pairs, since air temperature, humidity
and wind are uniform over a school.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.ndimage import maximum_filter

from neem_core.engine import HeatField
from neem_core.met import MetHour, Site
from neem_core.scene import ZONE_BUILDING, Scene
from neem_core.shadow import sunlit_fraction

LUT_STEP = 0.5  # C of Tmrt between lookup points
NEAR_CANOPY_CELLS = 5  # window for "canopy nearby", about the crown radius at 1 m
FEATURE_NAMES = ("sunlit", "under_canopy", "sunlit_x_svf", "near_canopy")


@dataclass(slots=True)
class HourModel:
    label: str
    altitude: float
    azimuth: float
    coef: tuple[float, ...]  # one per FEATURE_NAMES
    lut_tmrt: list[float]
    lut_utci: list[float]
    mae_changed: float  # Tmrt MAE on held-out changed cells, C


@dataclass(slots=True)
class Calibration:
    school_id: str
    hours: list[HourModel]

    def to_json(self) -> dict:
        return {
            "school_id": self.school_id,
            "features": list(FEATURE_NAMES),
            "near_canopy_cells": NEAR_CANOPY_CELLS,
            "hours": [
                {
                    "label": h.label,
                    "altitude": round(h.altitude, 4),
                    "azimuth": round(h.azimuth, 4),
                    "coef": [round(c, 5) for c in h.coef],
                    "lut_tmrt": h.lut_tmrt,
                    "lut_utci": [round(u, 3) for u in h.lut_utci],
                    "mae_changed": round(h.mae_changed, 3),
                }
                for h in self.hours
            ],
        }


def features(scene: Scene, svf: np.ndarray, altitude: float, azimuth: float) -> np.ndarray:
    """(rows, cols, 4) geometric features, see FEATURE_NAMES."""
    lit = sunlit_fraction(
        scene.dsm, scene.dem, scene.cdsm, scene.grid.pixel_size, altitude, azimuth
    )
    canopy = scene.cdsm > 0
    under = canopy.astype(np.float32)
    near = maximum_filter(canopy, size=NEAR_CANOPY_CELLS).astype(np.float32)
    return np.stack([lit, under, lit * svf, near], axis=-1)


def _lut(tmrt: np.ndarray, utci: np.ndarray) -> tuple[list[float], list[float]]:
    lo = float(np.floor(np.nanmin(tmrt) / LUT_STEP) * LUT_STEP) - 10
    hi = float(np.ceil(np.nanmax(tmrt) / LUT_STEP) * LUT_STEP) + 10
    grid = np.arange(lo, hi + LUT_STEP, LUT_STEP)
    ok = np.isfinite(tmrt) & np.isfinite(utci)
    t, u = tmrt[ok], utci[ok]
    order = np.argsort(t)
    t, u = t[order], u[order]
    slope, intercept = np.polyfit(t, u, 1)
    knots = np.interp(grid, t, u, left=np.nan, right=np.nan)
    knots = np.where(np.isnan(knots), slope * grid + intercept, knots)
    return grid.round(2).tolist(), np.maximum.accumulate(knots).tolist()


def fit(
    base_scene: Scene,
    base: HeatField,
    probe_scenes: Sequence[Scene],
    probes: Sequence[HeatField],
    site: Site,
    holdout: float = 0.25,
    seed: int = 0,
) -> Calibration:
    rng = np.random.default_rng(seed)
    keep = base_scene.zones != ZONE_BUILDING
    models: list[HourModel] = []
    for k, hour in enumerate(base.hours):
        sun = hour.sun(site)
        f_base = features(base_scene, base.svf, sun.altitude, sun.azimuth)
        xs, ys = [], []
        for scene, probe in zip(probe_scenes, probes, strict=True):
            dx = features(scene, base.svf, sun.altitude, sun.azimuth) - f_base
            dy = probe.tmrt[k] - base.tmrt[k]
            changed = keep & (np.abs(dx).sum(axis=-1) > 0) & np.isfinite(dy)
            xs.append(dx[changed])
            ys.append(dy[changed])
        X, y = np.concatenate(xs), np.concatenate(ys)
        test = rng.random(len(y)) < holdout
        coef, *_ = np.linalg.lstsq(X[~test], y[~test], rcond=None)
        mae = float(np.mean(np.abs(X[test] @ coef - y[test]))) if test.any() else 0.0
        lut_t, lut_u = _lut(base.tmrt[k][keep], base.utci[k][keep])
        models.append(
            HourModel(
                label=hour.label,
                altitude=sun.altitude,
                azimuth=sun.azimuth,
                coef=tuple(float(c) for c in coef),
                lut_tmrt=lut_t,
                lut_utci=lut_u,
                mae_changed=mae,
            )
        )
    return Calibration(school_id=base_scene.school_id, hours=models)


def predict(
    cal: Calibration, scene: Scene, base_scene: Scene, base: HeatField
) -> tuple[np.ndarray, np.ndarray]:
    """T0 Tmrt and UTCI for an edited scene, (hours, rows, cols) each."""
    tmrt, utci = [], []
    for k, h in enumerate(cal.hours):
        dx = features(scene, base.svf, h.altitude, h.azimuth) - features(
            base_scene, base.svf, h.altitude, h.azimuth
        )
        t = base.tmrt[k] + dx @ np.asarray(h.coef, dtype=np.float32)
        lut = np.interp(t, h.lut_tmrt, h.lut_utci) - np.interp(base.tmrt[k], h.lut_tmrt, h.lut_utci)
        tmrt.append(t)
        utci.append(base.utci[k] + lut)
    return np.stack(tmrt).astype(np.float32), np.stack(utci).astype(np.float32)


def school_hours(hours: Sequence[MetHour], start: int = 8, end: int = 14) -> list[MetHour]:
    return [h for h in hours if start <= h.time.hour <= end]
