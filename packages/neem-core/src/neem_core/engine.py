"""T1: the full SOLWEIG radiation budget behind a small, stable interface (ADR 0001)."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
import rasterio
import solweig

from neem_core.met import MetHour, Site
from neem_core.scene import Scene


@dataclass(slots=True)
class HeatField:
    """Hourly fields on the scene grid. Arrays are (hours, rows, cols)."""

    hours: list[MetHour]
    tmrt: np.ndarray
    utci: np.ndarray
    sunlit: np.ndarray
    svf: np.ndarray  # (rows, cols), sky view factor including vegetation
    timings: dict[str, float] = field(default_factory=dict)


class HeatEngine(Protocol):
    def run(self, scene: Scene, hours: Sequence[MetHour], site: Site) -> HeatField: ...


def scene_digest(scene: Scene) -> str:
    h = hashlib.blake2b(digest_size=12)
    for arr in (scene.dsm, scene.dem, scene.cdsm):
        h.update(np.ascontiguousarray(arr, dtype=np.float32).tobytes())
    h.update(repr(scene.grid).encode())
    return h.hexdigest()


class SolweigEngine:
    """Runs SOLWEIG with our sun positions, so T0 and T1 see the same sun."""

    def __init__(self, cache_dir: Path, use_gpu: bool = True) -> None:
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not use_gpu:
            solweig.disable_gpu()

    def run(self, scene: Scene, hours: Sequence[MetHour], site: Site) -> HeatField:
        t0 = time.perf_counter()
        work = self.cache_dir / scene_digest(scene)
        # prepare() rewrites its inputs in place (cdsm becomes absolute, with NaNs), so it
        # only ever sees copies.
        surface = solweig.SurfaceData.prepare(
            dsm=scene.dsm.astype(np.float32, copy=True),
            dem=scene.dem.astype(np.float32, copy=True),
            cdsm=scene.cdsm.astype(np.float32, copy=True),
            cdsm_relative=True,
            pixel_size=scene.grid.pixel_size,
            working_dir=str(work),
        )
        t1 = time.perf_counter()
        weather = []
        for h in hours:
            sun = h.sun(site)
            weather.append(
                solweig.Weather(
                    datetime=h.time,
                    ta=h.ta,
                    rh=h.rh,
                    global_rad=h.global_rad,
                    ws=max(h.ws, 0.5),
                    pressure=h.pressure,
                    measured_direct_rad=h.direct_rad,
                    measured_diffuse_rad=h.diffuse_rad,
                    precomputed_sun_altitude=sun.altitude,
                    precomputed_sun_azimuth=sun.azimuth,
                )
            )
        location = solweig.Location(
            latitude=site.latitude,
            longitude=site.longitude,
            altitude=site.altitude,
            utc_offset=site.utc_offset,
        )
        out = Path(tempfile.mkdtemp(prefix="solweig-", dir=self.cache_dir))
        try:
            solweig.calculate(
                surface=surface,
                weather=weather,
                location=location,
                output_dir=str(out),
                outputs=["tmrt", "utci", "shadow"],
            )
            t2 = time.perf_counter()
            tmrt = _stack(out, "tmrt", hours)
            utci = _stack(out, "utci", hours)
            sunlit = _stack(out, "shadow", hours)
        finally:
            shutil.rmtree(out, ignore_errors=True)
        svf = _svf(surface, scene.grid.shape)
        return HeatField(
            hours=list(hours),
            tmrt=tmrt,
            utci=utci,
            sunlit=sunlit,
            svf=svf,
            timings={
                "prepare_s": t1 - t0,
                "calculate_s": t2 - t1,
                "total_s": time.perf_counter() - t0,
            },
        )


def _stack(out: Path, kind: str, hours: Sequence[MetHour]) -> np.ndarray:
    layers = []
    for h in hours:
        path = out / kind / f"{kind}_{h.time:%Y%m%d_%H%M}.tif"
        with rasterio.open(path) as ds:
            layers.append(ds.read(1).astype(np.float32))
    return np.stack(layers)


def _svf(surface: solweig.SurfaceData, shape: tuple[int, int]) -> np.ndarray:
    svf = surface.svf
    for name in ("svf", "svf_total", "total"):
        arr = getattr(svf, name, None)
        if isinstance(arr, np.ndarray) and arr.shape == shape:
            return arr.astype(np.float32)
    if isinstance(svf, np.ndarray) and svf.shape == shape:
        return svf.astype(np.float32)
    raise RuntimeError(f"cannot find total SVF on {type(svf).__name__}")
