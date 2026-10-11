"""Heat ramp and map colours, one source of truth for the images (Python) and the site (TypeScript).

The ramp is continuous: its colour anchors are not band names. The heat-stress bands are the
UTCI assessment scale (Bröde et al. 2012), kept separately so a label always matches the value.
"""

from __future__ import annotations

import numpy as np

# (UTCI C, hex): colour anchors, linear between them, clamped at the ends
STOPS: list[tuple[float, str]] = [
    (26.0, "#E9EDF0"),
    (32.0, "#F1D9A7"),
    (38.0, "#E9A15A"),
    (42.0, "#D65A2E"),
    (46.0, "#8C1C30"),
]

# (lower bound C, name): the UTCI heat-stress categories; below the first is no heat stress
BANDS: list[tuple[float, str]] = [
    (26.0, "Moderate"),
    (32.0, "Strong"),
    (38.0, "Very strong"),
    (46.0, "Extreme"),
]
NO_HEAT_STRESS = "No heat stress"

# How a heat map is drawn. The 1 pm PNG and the live planner canvas must paint the same
# colours, or the swap from one to the other flashes.
SCHOOL_ROOF = "#d9d2c5"  # the school's own buildings
NEARBY_ROOF = "#e9e4da"  # anything else taller than TALL_M: roofs and walls next door
OUTSIDE_ALPHA = 56  # heat beyond the school wall, at 22% (56 of 255)
TALL_M = 2.5  # dsm - dem above this is a structure, not ground


def hex_to_rgb(hex_: str) -> tuple[int, int, int]:
    return int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16)


def colorize(utci: np.ndarray) -> np.ndarray:
    """(rows, cols) UTCI to (rows, cols, 3) uint8, linear between stops, clamped at the ends."""
    xs = np.array([s[0] for s in STOPS])
    rgb = np.array([hex_to_rgb(s[1]) for s in STOPS], dtype=float)
    v = np.nan_to_num(utci, nan=xs[0])
    out = np.stack([np.interp(v, xs, rgb[:, k]) for k in range(3)], axis=-1)
    return out.round().astype(np.uint8)


def band(utci: float) -> str:
    name = NO_HEAT_STRESS
    for lower, label in BANDS:
        if utci >= lower:
            name = label
    return name


def band_hex() -> list[str]:
    """A colour for each band, read off the ramp at its middle (4 C inside an open end)."""
    lows = [BANDS[0][0] - 8.0] + [lo for lo, _ in BANDS]
    highs = [lo for lo, _ in BANDS] + [BANDS[-1][0] + 8.0]
    mids = np.array([(lo + hi) / 2 for lo, hi in zip(lows, highs, strict=True)])
    return ["#{:02x}{:02x}{:02x}".format(*rgb) for rgb in colorize(mids[None, :])[0]]


def to_json() -> dict[str, object]:
    names = [NO_HEAT_STRESS] + [label for _, label in BANDS]
    lows: list[float | None] = [None] + [lo for lo, _ in BANDS]
    return {
        "stops": [{"utci": u, "hex": h} for u, h in STOPS],
        "bands": [
            {"min": lo, "name": n, "hex": h}
            for lo, n, h in zip(lows, names, band_hex(), strict=True)
        ],
        "map": {
            "school_roof": SCHOOL_ROOF,
            "nearby_roof": NEARBY_ROOF,
            "outside_alpha": OUTSIDE_ALPHA,
            "tall_m": TALL_M,
        },
    }
