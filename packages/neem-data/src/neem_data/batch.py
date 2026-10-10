"""City-scale ranking: one pure handler, two executors (ADR 0005)."""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd

from neem_core.exposure import exposure
from neem_data import lake
from neem_data.forcing import met_hours, site_for
from neem_data.scene_builder import build_scene, school_row

RANK_HOURS = (9, 11, 13)
RANK_PIXEL = 2.0


def rank_one(school_id: str, day: str) -> dict[str, Any]:
    """Coarse T2 run for one school. Never raises: failures come back as a row with an error."""
    started = time.perf_counter()
    row = school_row(school_id)
    base: dict[str, Any] = {
        "school_id": school_id,
        "name": row["name"],
        "government": bool(row["government"]),
        "area_m2": float(row["area_m2"]),
    }
    try:
        from neem_data.twin import engine

        scene, quality = build_scene(school_id, RANK_PIXEL)
        hours = [h for h in met_hours(day) if h.time.hour in RANK_HOURS]
        field = engine().run(scene, hours, site_for(scene))
        exp = exposure(scene, field.tmrt, field.utci, field.sunlit)
        thumb = lake.path("rank", day, "maps", f"{school_id}.npz")
        np.savez_compressed(
            thumb,
            utci=field.utci[-1].astype(np.float16),
            zones=scene.zones,
            pixel_size=scene.grid.pixel_size,
        )
        return (
            base
            | exp.to_json()
            | {
                "canopy_cover": round(quality.canopy_cover, 3),
                "height_coverage": round(quality.height_coverage, 3),
                "buildings": quality.buildings,
                "status": "ok",
                "error": None,
                "seconds": round(time.perf_counter() - started, 2),
            }
        )
    except Exception as exc:
        return base | {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "trace": traceback.format_exc(limit=3)[-800:],
            "seconds": round(time.perf_counter() - started, 2),
        }


class Executor(Protocol):
    def map(
        self, fn: Callable[[str, str], dict[str, Any]], items: Iterable[str], day: str
    ) -> Iterator[dict[str, Any]]: ...


class LocalPoolExecutor:
    def __init__(self, workers: int) -> None:
        self.workers = workers

    def map(
        self, fn: Callable[[str, str], dict[str, Any]], items: Iterable[str], day: str
    ) -> Iterator[dict[str, Any]]:
        with ProcessPoolExecutor(max_workers=self.workers) as pool:
            futures = [pool.submit(fn, item, day) for item in items]
            for f in as_completed(futures):
                yield f.result()


def rank_city(
    day: str, executor: Executor, limit: int | None = None, only_government: bool = False
) -> Path:
    import geopandas as gpd

    schools = gpd.read_parquet(lake.path(*lake.SCHOOLS))
    todo = schools[schools.has_grounds & (schools.area_m2 >= 500)]
    if only_government:
        todo = todo[todo.government]
    out = lake.path("rank", day, "schools.parquet")
    done: list[dict[str, Any]] = []
    if out.exists():
        prev = pd.read_parquet(out)
        done = cast(
            list[dict[str, Any]], prev.loc[prev["status"] == "ok"].to_dict(orient="records")
        )
    finished = {r["school_id"] for r in done}
    ids = [s for s in todo["school_id"].tolist() if s not in finished][: limit or None]
    print(f"rank: {len(finished)} already done, {len(ids)} to run")
    started = time.perf_counter()
    for i, row in enumerate(executor.map(rank_one, ids, day), 1):
        done.append(row)
        if i % 10 == 0 or i == len(ids):
            pd.DataFrame(done).to_parquet(out)
            rate = i / (time.perf_counter() - started)
            print(f"rank: {i}/{len(ids)} ({rate * 60:.0f}/min) last={row['status']} {row['name']}")
    pd.DataFrame(done).to_parquet(out)
    return out
