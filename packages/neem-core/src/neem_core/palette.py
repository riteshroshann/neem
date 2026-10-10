"""The heat ramp, one source of truth for thumbnails (Python) and the site (TypeScript).

Stops sit on the UTCI heat-stress bands, so a colour always means a physiological category.
"""

from __future__ import annotations

import numpy as np

# (UTCI lower bound C, hex, band)
STOPS: list[tuple[float, str, str]] = [
    (26.0, "#E9EDF0", "No heat stress"),
    (32.0, "#F1D9A7", "Moderate"),
    (38.0, "#E9A15A", "Strong"),
    (42.0, "#D65A2E", "Very strong"),
    (46.0, "#8C1C30", "Extreme"),
]


def _rgb(hex_: str) -> tuple[int, int, int]:
    return int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16)


def colorize(utci: np.ndarray) -> np.ndarray:
    """(rows, cols) UTCI to (rows, cols, 3) uint8, linear between stops, clamped at the ends."""
    xs = np.array([s[0] for s in STOPS])
    rgb = np.array([_rgb(s[1]) for s in STOPS], dtype=float)
    v = np.nan_to_num(utci, nan=xs[0])
    out = np.stack([np.interp(v, xs, rgb[:, k]) for k in range(3)], axis=-1)
    return out.round().astype(np.uint8)


def to_json() -> list[dict[str, object]]:
    return [{"utci": u, "hex": h, "band": b} for u, h, b in STOPS]
