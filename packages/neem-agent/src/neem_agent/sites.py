"""Where to plant: the hottest open spots of a yard, spread at least a crown apart."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.ndimage import distance_transform_edt

from neem_core.scene import ZONE_BUILDING, ZONE_GROUND, Scene

BUILDING_CLEARANCE_M = 2.0  # roots and foundations


def plantable(scene: Scene, taken: Sequence[tuple[float, float, float]] = ()) -> np.ndarray:
    """Open school ground with no canopy, clear of buildings and of circles in `taken`."""
    px = scene.grid.pixel_size
    dist = np.asarray(distance_transform_edt(scene.zones != ZONE_BUILDING), dtype=float)
    clear = dist * px >= BUILDING_CLEARANCE_M
    ok = (scene.zones == ZONE_GROUND) & (scene.cdsm <= 0) & clear
    if taken:
        xs, ys = scene.grid.cell_centres()
        for x, y, r in taken:
            ok &= (xs - x) ** 2 + (ys - y) ** 2 > r**2
    return ok


def hottest_sites(
    scene: Scene,
    heat: np.ndarray,
    count: int,
    spacing_m: float,
    taken: Sequence[tuple[float, float, float]] = (),
) -> list[tuple[float, float]]:
    """Greedy non-maximum suppression over `heat` (rows, cols): hottest first, `spacing_m` apart."""
    ok = plantable(scene, taken)
    rows, cols = np.nonzero(ok & np.isfinite(heat))
    if len(rows) == 0 or count <= 0:
        return []
    order = np.argsort(-heat[rows, cols], kind="stable")
    xs, ys = scene.grid.cell_centres()
    px, py = xs[rows, cols][order], ys[rows, cols][order]
    picked: list[tuple[float, float]] = []
    alive = np.ones(len(order), dtype=bool)
    for i in range(len(order)):
        if not alive[i]:
            continue
        picked.append((float(px[i]), float(py[i])))
        if len(picked) == count:
            break
        alive &= (px - px[i]) ** 2 + (py - py[i]) ** 2 >= spacing_m**2
    return picked
