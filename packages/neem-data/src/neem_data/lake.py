"""Where pipeline artefacts live on local disk. Layout mirrors s3://neem-lake (ADR 0003)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("NEEM_LAKE", Path.cwd() / "data" / "lake"))


def path(*parts: str) -> Path:
    p = ROOT.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


SCHOOLS = ("raw", "osm", "schools.parquet")
BUILDINGS = ("raw", "overture", "buildings.parquet")


def scene_dir(school_id: str) -> Path:
    return ROOT / "scenes" / school_id


def run_dir(school_id: str, run_id: str) -> Path:
    return ROOT / "runs" / school_id / run_id
