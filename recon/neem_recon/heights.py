"""Measured heights from a registered cloud, written back onto the school's 1 m grid."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import label

GREEN = 0.06  # excess-green above this is vegetation
MIN_POINTS = 3  # per 1 m cell before we trust a height


@dataclass(frozen=True)
class SceneArrays:
    dsm: np.ndarray
    dem: np.ndarray
    cdsm: np.ndarray
    zones: np.ndarray
    x0: float
    y0: float
    pixel: float

    @classmethod
    def load(cls, scene_dir: Path) -> SceneArrays:
        meta = json.loads((scene_dir / "scene.json").read_text())
        with np.load(scene_dir / "scene.npz") as z:
            g = meta["grid"]
            return cls(z["dsm"], z["dem"], z["cdsm"], z["zones"], g["x0"], g["y0"], g["pixel_size"])

    def cells(self, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        cols = np.floor((xy[:, 0] - self.x0) / self.pixel).astype(int)
        rows = np.floor((self.y0 - xy[:, 1]) / self.pixel).astype(int)
        ok = (rows >= 0) & (rows < self.dsm.shape[0]) & (cols >= 0) & (cols < self.dsm.shape[1])
        return rows, cols, ok


def max_raster(s: SceneArrays, xy: np.ndarray, h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows, cols, ok = s.cells(xy)
    top = np.zeros(s.dsm.shape, dtype=np.float32)
    count = np.zeros(s.dsm.shape, dtype=np.int32)
    np.maximum.at(top, (rows[ok], cols[ok]), h[ok])
    np.add.at(count, (rows[ok], cols[ok]), 1)
    return top, count


def measure(s: SceneArrays, xy: np.ndarray, h: np.ndarray, exg: np.ndarray) -> dict:
    """New DSM and CDSM where the cloud saw enough; a report of what changed."""
    built = (h > 2.0) & (exg <= GREEN)
    green = (h > 2.0) & (exg > GREEN)
    b_top, b_n = max_raster(s, xy[built], h[built])
    g_top, g_n = max_raster(s, xy[green], h[green])

    prior = s.dsm - s.dem
    footprints, n = label(prior > 0)
    dsm = s.dsm.copy()
    measured = []
    for k in range(1, n + 1):
        cells = footprints == k
        seen = cells & (b_n >= MIN_POINTS)
        if seen.sum() < max(4, 0.15 * cells.sum()):
            continue  # the camera did not see enough of this building
        height = float(np.percentile(b_top[seen], 90))
        measured.append(
            {
                "cells": int(cells.sum()),
                "prior_m": round(float(np.median(prior[cells])), 2),
                "measured_m": round(height, 2),
            }
        )
        dsm[cells] = s.dem[cells] + height
    open_ground = (prior <= 0) & (g_n >= MIN_POINTS)
    cdsm = np.where(open_ground, np.maximum(s.cdsm, g_top), s.cdsm).astype(np.float32)
    return {
        "dsm": dsm.astype(np.float32),
        "cdsm": cdsm,
        "buildings_measured": measured,
        "tree_cells_added": int((open_ground & (s.cdsm <= 0)).sum()),
    }
