"""Heat exposure metrics over the places children use."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from neem_core.scene import ZONE_GROUND, Scene

# UTCI heat stress categories (Bröde et al. 2012), lower bounds in C
UTCI_STRONG = 32.0
UTCI_VERY_STRONG = 38.0
UTCI_EXTREME = 46.0


@dataclass(frozen=True, slots=True)
class Exposure:
    utci_mean: float  # mean over ground cells and school hours
    utci_peak_hour_mean: float  # ground mean at the hottest hour
    extreme_fraction: float  # share of ground cell-hours above 46 C UTCI
    very_strong_fraction: float  # share above 38 C
    shade_fraction: float  # share of ground cell-hours in shade (sunlit < 0.5)
    tmrt_mean: float
    ground_m2: float

    def to_json(self) -> dict:
        return {k: round(v, 3) for k, v in asdict(self).items()}


def exposure(scene: Scene, tmrt: np.ndarray, utci: np.ndarray, sunlit: np.ndarray) -> Exposure:
    ground = scene.mask(ZONE_GROUND)
    if not ground.any():
        raise ValueError(f"{scene.school_id} has no open ground")
    u = utci[:, ground]
    hourly = np.nanmean(u, axis=1)
    return Exposure(
        utci_mean=float(np.nanmean(u)),
        utci_peak_hour_mean=float(np.nanmax(hourly)),
        extreme_fraction=float(np.mean(u > UTCI_EXTREME)),
        very_strong_fraction=float(np.mean(u > UTCI_VERY_STRONG)),
        shade_fraction=float(np.mean(sunlit[:, ground] < 0.5)),
        tmrt_mean=float(np.nanmean(tmrt[:, ground])),
        ground_m2=float(ground.sum() * scene.grid.pixel_size**2),
    )
