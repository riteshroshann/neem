"""Cross-language differential test, Python half.

The browser runs a TypeScript port of the T0 geometry. This writes (with NEEM_WRITE_FIXTURE=1)
or checks a shared fixture of inputs and Python outputs; web/src/lib/physics.test.ts asserts
the TypeScript reproduces them. If the Python changes, the fixture check fails until the
fixture is regenerated and the TypeScript is shown to still agree.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter

from neem_core.grid import Grid
from neem_core.interventions import ShadeSail, Tree, apply
from neem_core.scene import ZONE_BUILDING, ZONE_GROUND, Scene
from neem_core.shadow import sunlit_fraction
from neem_core.surrogate import NEAR_CANOPY_CELLS

FIXTURE = Path(__file__).parents[3] / "web" / "src" / "lib" / "fixtures" / "physics.json"
SUNS = [(18.0, 95.0), (52.0, 140.0), (74.9, 190.1)]


def _scene() -> Scene:
    n = 40
    grid = Grid(x0=700_000.0, y0=3_180_000.0, pixel_size=1.0, rows=n, cols=n)
    dem = np.round(np.full((n, n), 210.0) + np.linspace(0, 0.6, n)[None, :], 2)
    dsm = dem.copy()
    zones = np.full((n, n), ZONE_GROUND, dtype=np.uint8)
    dsm[6:16, 8:30] += 11.5
    zones[6:16, 8:30] = ZONE_BUILDING
    cdsm = np.zeros((n, n))
    yy, xx = np.mgrid[0:n, 0:n]
    cdsm[(yy - 28) ** 2 + (xx - 12) ** 2 <= 9] = 6.0
    return Scene(
        "fixture",
        "Fixture",
        grid,
        dsm.astype(np.float32),
        dem.astype(np.float32),
        cdsm.astype(np.float32),
        zones,
    )


def _compute() -> dict:
    s = _scene()
    design = [
        Tree(*s.grid.to_map(30.2, 25.7), "neem"),
        Tree(*s.grid.to_map(22.5, 33.0), "peepal"),
        ShadeSail(*s.grid.to_map(34.0, 6.0), 6.0, 4.0),
    ]
    edited = apply(s, design)
    near = maximum_filter(edited.cdsm > 0, size=NEAR_CANOPY_CELLS)
    return {
        "grid": {
            "rows": s.grid.rows,
            "cols": s.grid.cols,
            "pixel_size": s.grid.pixel_size,
            "x0": s.grid.x0,
            "y0": s.grid.y0,
        },
        "dsm": s.dsm.round(2).ravel().tolist(),
        "dem": s.dem.round(2).ravel().tolist(),
        "cdsm": s.cdsm.round(2).ravel().tolist(),
        "zones": s.zones.ravel().tolist(),
        "design": [
            {"kind": "tree", "x": d.x, "y": d.y, "species": d.species}
            if isinstance(d, Tree)
            else {"kind": "sail", "x": d.x, "y": d.y, "width": d.width, "depth": d.depth}
            for d in design
        ],
        "suns": [list(sun) for sun in SUNS],
        "sunlit": [
            sunlit_fraction(s.dsm, s.dem, s.cdsm, 1.0, alt, az).round(4).ravel().tolist()
            for alt, az in SUNS
        ],
        "edited_cdsm": edited.cdsm.round(4).ravel().tolist(),
        "edited_near": near.astype(int).ravel().tolist(),
    }


def test_web_fixture_matches_python() -> None:
    current = _compute()
    if os.environ.get("NEEM_WRITE_FIXTURE") == "1" or not FIXTURE.exists():
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(current))
    saved = json.loads(FIXTURE.read_text())
    assert saved == current, "Python T0 changed; regenerate with NEEM_WRITE_FIXTURE=1"
