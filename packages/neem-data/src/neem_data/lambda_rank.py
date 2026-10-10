"""Lambda entry points for the city ranking on a Step Functions Distributed Map (ADR 0005).

`handler` is the item processor: the same `rank_one` the local process pool runs. `collect`
runs once after the map and folds the rows into the ranking table.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from neem_data import lake
from neem_data.batch import rank_one

_synced = False


def _cold_start() -> None:
    global _synced
    if not _synced:
        lake.sync_from_s3(["raw/osm/", "raw/overture/", "raw/met/"])
        _synced = True


def handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    """One school. Event: {"school_id": ..., "day": ...}."""
    _cold_start()
    row = rank_one(str(event["school_id"]), str(event["day"]))
    out = lake.path("rank", str(event["day"]), "rows", f"{event['school_id']}.json")
    out.write_text(json.dumps(row, default=str))
    lake.upload(out)
    thumb = lake.ROOT / "rank" / str(event["day"]) / "maps" / f"{event['school_id']}.npz"
    if thumb.exists():
        lake.upload(thumb)
    return {"school_id": row["school_id"], "status": row["status"]}


def collect(event: dict[str, Any], _context: object) -> dict[str, Any]:
    """Merge every row file for a day into rank/<day>/schools.parquet."""
    day = str(event["day"])
    lake.sync_from_s3([f"rank/{day}/rows/"])
    rows = [json.loads(p.read_text()) for p in (lake.ROOT / "rank" / day / "rows").glob("*.json")]
    out = lake.path("rank", day, "schools.parquet")
    pd.DataFrame(rows).to_parquet(out)
    lake.upload(out)
    ok = sum(r.get("status") == "ok" for r in rows)
    return {"day": day, "rows": len(rows), "ok": ok}
