"""Design changes a school can make, applied to a scene as pure functions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from neem_core.scene import ZONE_BUILDING, Scene

Species = Literal["neem", "peepal", "jamun", "amaltas"]

# Canopy at about five years after planting a nursery sapling: (height m, crown radius m, cost Rs).
# Cost covers sapling, guard, pit and two years of care.
SPECIES: dict[str, tuple[float, float, int]] = {
    "neem": (7.0, 3.5, 3_500),
    "peepal": (8.0, 4.5, 3_500),
    "jamun": (7.5, 3.5, 3_500),
    "amaltas": (6.0, 3.0, 3_000),
}

SAIL_COST_PER_M2 = 1_800  # HDPE shade sail with steel posts, installed

# A neem's canopy by age, (height m, crown radius m): our assumption, inside published ranges.
# Neem grows fast, about 7 m in five years, and reaches 15 to 20 m with a crown 10 to 20 m
# wide when mature. Used to show what one planting becomes; the planner always plans at five years.
NEEM_BY_AGE: dict[int, tuple[float, float]] = {
    1: (2.0, 0.75),
    5: SPECIES["neem"][:2],
    10: (10.0, 5.0),
    20: (13.0, 6.0),
    30: (15.0, 7.0),
}


@dataclass(frozen=True, slots=True)
class Tree:
    x: float  # map coordinates, metres
    y: float
    species: Species = "neem"
    size: tuple[float, float] | None = None  # (height, crown radius) when not the five-year canopy

    @property
    def height(self) -> float:
        return self.size[0] if self.size else SPECIES[self.species][0]

    @property
    def radius(self) -> float:
        return self.size[1] if self.size else SPECIES[self.species][1]

    @property
    def cost(self) -> int:
        return SPECIES[self.species][2]


@dataclass(frozen=True, slots=True)
class ShadeSail:
    """A horizontal sail over a rectangle, modelled as dense canopy at mast height."""

    x: float  # centre, map coordinates
    y: float
    width: float  # east-west, metres
    depth: float  # north-south, metres
    height: float = 4.0

    @property
    def cost(self) -> int:
        return round(self.width * self.depth * SAIL_COST_PER_M2)


Intervention = Tree | ShadeSail


def apply(scene: Scene, interventions: Sequence[Intervention]) -> Scene:
    """Return a new scene with the interventions added. The input is not modified.

    Trees and sails only add canopy; they never lower existing canopy, and nothing is planted
    on a roof.
    """
    cdsm = scene.cdsm.copy()
    xs, ys = scene.grid.cell_centres()
    on_roof = scene.zones == ZONE_BUILDING
    for item in interventions:
        if isinstance(item, Tree):
            d2 = (xs - item.x) ** 2 + (ys - item.y) ** 2
            # Ellipsoidal crown: tallest at the trunk, tapering toward the edge.
            r2 = item.radius**2
            inside = d2 <= r2
            crown = item.height * np.sqrt(np.clip(1.0 - d2 / r2, 0.0, 1.0)) ** 0.5
            layer = np.where(inside, crown, 0.0)
        else:
            inside = (np.abs(xs - item.x) <= item.width / 2) & (
                np.abs(ys - item.y) <= item.depth / 2
            )
            layer = np.where(inside, item.height, 0.0)
        layer = np.where(on_roof, 0.0, layer)
        np.maximum(cdsm, layer, out=cdsm)
    return replace(scene, cdsm=cdsm.astype(np.float32))


def total_cost(interventions: Sequence[Intervention]) -> int:
    return sum(item.cost for item in interventions)
