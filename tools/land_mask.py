"""Land mask for the hero globe: Natural Earth land at half a degree, run-length encoded.

uv run --no-project --with shapely --with numpy python tools/land_mask.py ne_110m_land.geojson
"""

from __future__ import annotations

import json
import string
import sys
from pathlib import Path

import numpy as np
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import unary_union

STEP = 0.5
ALPHABET = string.digits + string.ascii_letters + "-_"  # 64 symbols, two per run


def mask(geojson: Path) -> np.ndarray:
    features = json.loads(geojson.read_text())["features"]
    land = unary_union([shape(f["geometry"]) for f in features])
    lats = 90 - STEP / 2 - np.arange(int(180 / STEP)) * STEP
    lons = -180 + STEP / 2 + np.arange(int(360 / STEP)) * STEP
    lon, lat = np.meshgrid(lons, lats)
    return contains_xy(land, lon, lat)


def encode(m: np.ndarray) -> str:
    """Each row as alternating sea/land run lengths, starting with sea; rows end with '.'."""
    rows = []
    for row in m:
        runs, value, n = [], False, 0
        for v in row:
            if v == value:
                n += 1
            else:
                runs.append(n)
                value, n = bool(v), 1
        runs.append(n)
        rows.append("".join(ALPHABET[r // 64] + ALPHABET[r % 64] for r in runs))
    return ".".join(rows)


def main() -> None:
    m = mask(Path(sys.argv[1]))
    rle = encode(m)
    rows, cols = m.shape
    out = Path("web/src/art/land.ts")
    out.write_text(
        "// Natural Earth 1:110m land, 0.5 degree cells, north first. Made by tools/land_mask.py.\n"
        f"export const LAND = {{ cols: {cols}, rows: {rows}, rle: {json.dumps(rle)} }};\n",
        newline="\n",
    )
    print(f"{out}: {m.mean():.1%} land, {len(rle) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
