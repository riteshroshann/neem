"""Synthetic schoolyards shared by the core tests."""

from __future__ import annotations

import numpy as np
from neem_core.grid import Grid
from neem_core.scene import ZONE_BUILDING, ZONE_GROUND, Scene

GROUND = 210.0  # metres above sea level, typical for north-west Delhi


def yard(rows: int = 120, cols: int = 120, pixel_size: float = 1.0) -> Scene:
    """An L-shaped school block, open ground to the south, one existing tree."""
    grid = Grid(x0=700_000.0, y0=3_180_000.0, pixel_size=pixel_size, rows=rows, cols=cols)
    dem = np.full(grid.shape, GROUND, dtype=np.float32)
    dsm = dem.copy()
    zones = np.full(grid.shape, ZONE_GROUND, dtype=np.uint8)
    blocks = [(10, 30, 10, 90, 12.0), (30, 70, 10, 30, 9.0)]  # r0, r1, c0, c1, height
    for r0, r1, c0, c1, h in blocks:
        dsm[r0:r1, c0:c1] = GROUND + h
        zones[r0:r1, c0:c1] = ZONE_BUILDING
    cdsm = np.zeros(grid.shape, dtype=np.float32)
    yy, xx = np.mgrid[0:rows, 0:cols]
    cdsm[(yy - 85) ** 2 + (xx - 60) ** 2 <= 16] = 7.0
    return Scene("fixture-yard", "Fixture Yard", grid, dsm, dem, cdsm, zones)
