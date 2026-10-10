"""A school scene: surface rasters plus the zones children actually use."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from neem_core.grid import Grid

# Zone codes in the zones raster. 0 means outside the school or unused.
ZONE_NONE = 0
ZONE_GROUND = 1  # open ground: assembly, recess, games
ZONE_BUILDING = 2  # school buildings (roofs)
ZONE_PATH = 3  # route from the gate to the street


@dataclass(slots=True)
class Scene:
    """Everything SOLWEIG and the fast tier need for one school.

    dsm: absolute surface height (ground + buildings), metres
    dem: absolute ground height, metres
    cdsm: canopy height above ground, metres (0 where there is no tree)
    zones: uint8 zone codes, see ZONE_*
    """

    school_id: str
    name: str
    grid: Grid
    dsm: np.ndarray
    dem: np.ndarray
    cdsm: np.ndarray
    zones: np.ndarray
    provenance: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for layer in ("dsm", "dem", "cdsm", "zones"):
            arr = getattr(self, layer)
            if arr.shape != self.grid.shape:
                raise ValueError(f"{layer} has shape {arr.shape}, grid is {self.grid.shape}")
        if np.any(self.dsm < self.dem - 0.5):
            raise ValueError("dsm is below dem; dsm must be absolute and include the ground")
        if np.any(self.cdsm < 0):
            raise ValueError("cdsm must be height above ground, never negative")

    @property
    def building_height(self) -> np.ndarray:
        return self.dsm - self.dem

    def mask(self, zone: int) -> np.ndarray:
        return self.zones == zone

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            directory / "scene.npz",
            dsm=self.dsm.astype(np.float32),
            dem=self.dem.astype(np.float32),
            cdsm=self.cdsm.astype(np.float32),
            zones=self.zones.astype(np.uint8),
        )
        meta = {
            "school_id": self.school_id,
            "name": self.name,
            "grid": asdict(self.grid),
            "provenance": self.provenance,
        }
        (directory / "scene.json").write_text(json.dumps(meta, indent=2))

    @classmethod
    def load(cls, directory: Path) -> Scene:
        meta = json.loads((directory / "scene.json").read_text())
        with np.load(directory / "scene.npz") as z:
            return cls(
                school_id=meta["school_id"],
                name=meta["name"],
                grid=Grid(**meta["grid"]),
                dsm=z["dsm"],
                dem=z["dem"],
                cdsm=z["cdsm"],
                zones=z["zones"],
                provenance=meta.get("provenance", {}),
            )
