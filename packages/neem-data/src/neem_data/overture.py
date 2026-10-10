"""Overture building footprints and heights for Delhi, pulled from S3 with DuckDB."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import duckdb
import httpx

from neem_data.aoi import DELHI_BBOX
from neem_data.http import get_json
from neem_data.sources import OVERTURE_BUCKET, OVERTURE_RELEASE, USER_AGENT

STAC = f"https://stac.overturemaps.org/{OVERTURE_RELEASE}/buildings/building/collection.json"
PREFIX = f"release/{OVERTURE_RELEASE}/theme=buildings/type=building/"
_PART = re.compile(r"part-(\d{5})-")


def overlapping_files(bbox: tuple[float, float, float, float]) -> list[str]:
    """S3 URLs of the release files whose extent overlaps bbox.

    The STAC collection lists one extent per file, in part-number order, after the overall
    extent. Scanning 3 files instead of 512 turns a 30 minute job into a minute.
    """
    minx, miny, maxx, maxy = bbox
    extents = get_json(STAC)["extent"]["spatial"]["bbox"][1:]
    wanted = {
        i
        for i, b in enumerate(extents)
        if b[0] < maxx and b[2] > minx and b[1] < maxy and b[3] > miny
    }
    keys = _list_keys()
    return [f"s3://{OVERTURE_BUCKET}/{k}" for k in keys if int(_PART.search(k).group(1)) in wanted]  # type: ignore[union-attr]


def _list_keys() -> list[str]:
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys: list[str] = []
    token: str | None = None
    while True:
        params = {"list-type": "2", "prefix": PREFIX}
        if token:
            params["continuation-token"] = token
        r = httpx.get(
            f"https://{OVERTURE_BUCKET}.s3.amazonaws.com/",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        r.raise_for_status()
        root = ET.fromstring(r.text)
        keys += [k.text or "" for k in root.findall("s3:Contents/s3:Key", ns)]
        nxt = root.find("s3:NextContinuationToken", ns)
        if nxt is None or not nxt.text:
            return [k for k in keys if k.endswith(".parquet")]
        token = nxt.text


def extract_buildings(out: Path, bbox: tuple[float, float, float, float] = DELHI_BBOX) -> int:
    """Write the buildings inside bbox to GeoParquet. Returns the number of buildings."""
    minx, miny, maxx, maxy = bbox
    files = overlapping_files(bbox)
    print(f"overture: {len(files)} of the release's files overlap the AOI")
    con = duckdb.connect()
    for stmt in (
        "INSTALL spatial; LOAD spatial;",
        "INSTALL httpfs; LOAD httpfs;",
        "SET s3_region='us-west-2';",
        "SET http_retries=8; SET http_retry_wait_ms=2000; SET http_timeout=120000;",
        "SET enable_progress_bar=true; SET threads=8;",
    ):
        con.execute(stmt)
    sources = ", ".join(f"'{f}'" for f in files)
    tmp = out.with_suffix(".tmp.parquet")
    started = time.perf_counter()
    con.execute(
        f"""
        COPY (
          SELECT id, height, num_floors, geometry
          FROM read_parquet([{sources}])
          WHERE bbox.xmin < {maxx} AND bbox.xmax > {minx}
            AND bbox.ymin < {maxy} AND bbox.ymax > {miny}
        ) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    tmp.replace(out)
    row = con.execute(f"SELECT count(*) FROM '{out.as_posix()}'").fetchone()
    count = int(row[0]) if row else 0
    print(f"overture: {count:,} buildings in {time.perf_counter() - started:.0f}s -> {out}")
    return count
