"""Fast shadow casting on a 2.5D surface: the geometric half of the T0 preview tier.

Each cell marches a ray toward the sun. A building taller than the ray blocks it; a tree crown
the ray passes through lets a fraction of the beam through. The same algorithm is ported to
TypeScript for the browser, and a differential test pins both to SOLWEIG's own shadows.
"""

from __future__ import annotations

import math

import numba
import numpy as np

# Fraction of the direct beam that passes through a dense crown (UMEP default is 3%).
CANOPY_TRANSMISSIVITY = 0.03
TRUNK_RATIO = 0.25  # trunk zone as a fraction of tree height; light passes below it


def sunlit_fraction(
    dsm: np.ndarray,
    dem: np.ndarray,
    cdsm: np.ndarray,
    pixel_size: float,
    altitude: float,
    azimuth: float,
    transmissivity: float = CANOPY_TRANSMISSIVITY,
    trunk_ratio: float = TRUNK_RATIO,
) -> np.ndarray:
    """Fraction of the direct beam reaching each cell's surface: 1 sunlit, 0 fully shaded.

    altitude and azimuth are in degrees; azimuth is clockwise from north. Night returns zeros.
    """
    if altitude <= 0:
        return np.zeros(dsm.shape, dtype=np.float32)
    return _cast(
        np.ascontiguousarray(dsm, dtype=np.float32),
        np.ascontiguousarray(dem, dtype=np.float32),
        np.ascontiguousarray(cdsm, dtype=np.float32),
        float(pixel_size),
        math.radians(altitude),
        math.radians(azimuth),
        float(transmissivity),
        float(trunk_ratio),
    )


@numba.njit(parallel=True, cache=True, fastmath=False)
def _cast(
    dsm: np.ndarray,
    dem: np.ndarray,
    cdsm: np.ndarray,
    pixel_size: float,
    alt: float,
    az: float,
    tau: float,
    trunk_ratio: float,
) -> np.ndarray:
    rows, cols = dsm.shape
    out = np.ones((rows, cols), dtype=np.float32)
    # Unit step toward the sun in grid space: east is +col, north is -row.
    dc = math.sin(az)
    dr = -math.cos(az)
    scale = 1.0 / max(abs(dc), abs(dr))
    dc *= scale
    dr *= scale
    step_m = scale * pixel_size
    rise = step_m * math.tan(alt)

    top = 0.0
    for r in range(rows):
        for c in range(cols):
            h = max(dsm[r, c], dem[r, c] + cdsm[r, c])
            top = max(top, h)

    for r in numba.prange(rows):
        for c in range(cols):
            z0 = dsm[r, c]
            # A cell under its own crown starts in shade.
            light = 1.0
            if cdsm[r, c] > 0.0 and dem[r, c] + cdsm[r, c] * trunk_ratio > z0 - 0.01:
                light = tau
            z = z0
            fr = float(r)
            fc = float(c)
            while True:
                fr += dr
                fc += dc
                z += rise
                if z > top:
                    break
                rr = math.floor(fr + 0.5)
                cc = math.floor(fc + 0.5)
                if rr < 0 or rr >= rows or cc < 0 or cc >= cols:
                    break
                if dsm[rr, cc] > z:
                    light = 0.0
                    break
                ch = cdsm[rr, cc]
                if ch > 0.0:
                    g = dem[rr, cc]
                    if g + ch > z and g + ch * trunk_ratio < z:
                        light = min(light, tau)
            out[r, c] = light
    return out
