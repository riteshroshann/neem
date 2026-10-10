"""Where pipeline artefacts live. Layout mirrors s3://<bucket> (ADR 0003).

Locally the lake is a folder. On Lambda it is a bucket (NEEM_LAKE_BUCKET): a cold start copies
the prefixes a function reads into /tmp, and `upload` pushes back what it writes.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(os.environ.get("NEEM_LAKE", Path.cwd() / "data" / "lake"))
BUCKET = os.environ.get("NEEM_LAKE_BUCKET")


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


def _s3():
    import boto3

    return boto3.client("s3", endpoint_url=os.environ.get("NEEM_AWS_ENDPOINT_URL"))


def sync_from_s3(prefixes: Iterable[str]) -> int:
    """Copy objects under `prefixes` from the lake bucket into ROOT. Returns files copied."""
    if not BUCKET:
        return 0
    s3, copied = _s3(), 0
    for prefix in prefixes:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                dst = ROOT / obj["Key"]
                if dst.exists() and dst.stat().st_size == obj["Size"]:
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(BUCKET, obj["Key"], str(dst))
                copied += 1
    return copied


def upload(local: Path) -> None:
    """Push one lake file back to the bucket (no-op when the lake is local)."""
    if BUCKET:
        _s3().upload_file(str(local), BUCKET, local.relative_to(ROOT).as_posix())
