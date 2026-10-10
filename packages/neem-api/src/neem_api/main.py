"""Neem HTTP API."""

from __future__ import annotations

from functools import cache
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from neem_api import read_model
from neem_api.jobs import (
    DynamoJobStore,
    FileJobStore,
    JobQueue,
    JobStore,
    SqsJobQueue,
    ThreadJobQueue,
    new_job,
)
from neem_api.settings import settings
from neem_core import __version__
from neem_data import lake

app = FastAPI(title="Neem", version=__version__, summary="Heat twins for Delhi schoolyards")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware, allow_origins=settings().cors_origins, allow_methods=["*"], allow_headers=["*"]
)


@cache
def backends() -> tuple[JobStore, JobQueue]:
    s = settings()
    if s.jobs == "aws":
        return DynamoJobStore(s), SqsJobQueue(s)
    store = FileJobStore(lake.ROOT / "jobs")
    return store, ThreadJobQueue(store)


class TreeIn(BaseModel):
    x: float = Field(description="easting, EPSG:32643 metres")
    y: float = Field(description="northing, EPSG:32643 metres")
    species: Literal["neem", "peepal", "jamun", "amaltas"] = "neem"


class SailIn(BaseModel):
    x: float
    y: float
    width: float = Field(gt=0, le=40)
    depth: float = Field(gt=0, le=40)


class DesignIn(BaseModel):
    trees: list[TreeIn] = Field(default_factory=list, max_length=200)
    sails: list[SailIn] = Field(default_factory=list, max_length=40)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "day": settings().day}


@app.get("/schools")
def list_schools(
    order: Literal["hottest", "coolest"] = "hottest",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    government: bool | None = None,
) -> dict[str, Any]:
    day = settings().day
    df = read_model.ranking(day)
    total = len(df)
    if df.empty:
        return {"day": day, "total": 0, "schools": []}
    if government is not None:
        df = df.loc[df["government"] == government]
    ranked = df.sort_values(by=["utci_mean"], ascending=[order == "coolest"]).head(limit)
    rows = ranked.to_dict(orient="records")
    for r in rows:
        r["has_twin"] = read_model.has_twin(str(r["school_id"]), day)
    return {"day": day, "total": total, "schools": rows}


@app.get("/schools/{school_id}")
def school(school_id: str) -> dict[str, Any]:
    day = settings().day
    if not read_model.has_twin(school_id, day):
        raise HTTPException(404, f"no twin for {school_id} on {day}")
    return read_model.twin_summary(school_id, day)


@app.get("/schools/{school_id}/layers.bin")
def layers(school_id: str) -> Response:
    day = settings().day
    if not read_model.has_twin(school_id, day):
        raise HTTPException(404, f"no twin for {school_id} on {day}")
    payload, ref = read_model.layers_bin(school_id, day)
    return Response(
        payload,
        media_type="application/octet-stream",
        headers={"X-Height-Ref": f"{ref:.3f}", "Cache-Control": "public, max-age=3600"},
    )


@app.get("/schools/{school_id}/calibration")
def calibration(school_id: str) -> dict[str, Any]:
    return read_model.calibration(school_id, settings().day)


@app.get("/schools/{school_id}/child")
def child(school_id: str) -> dict[str, Any]:
    return read_model.child(school_id, settings().day)


@app.post("/schools/{school_id}/designs", status_code=202)
def submit_design(school_id: str, design: DesignIn) -> dict[str, str]:
    day = settings().day
    if not read_model.has_twin(school_id, day):
        raise HTTPException(404, f"no twin for {school_id} on {day}")
    store, queue = backends()
    job = new_job(school_id, design.model_dump() | {"day": day})
    store.put(job)
    queue.submit(job)
    return {"job_id": job["job_id"], "state": job["state"]}


@app.get("/jobs/{job_id}")
def job(job_id: str) -> dict[str, Any]:
    found = backends()[0].get(job_id)
    if found is None:
        raise HTTPException(404, f"no job {job_id}")
    return found


def run() -> None:
    import uvicorn

    s = settings()
    uvicorn.run("neem_api.main:app", host=s.host, port=s.port, reload=False)
