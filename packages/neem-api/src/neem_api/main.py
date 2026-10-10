"""Neem HTTP API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from neem_api import read_model
from neem_api.authz import Decision, Identity, RecentJobs, check, identity_from_token
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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # On Lambda the lake is a bucket: pull what the read side serves into /tmp once.
    lake.sync_from_s3(["scenes/", "runs/", "rank/", "raw/met/", "raw/osm/", "approved/"])
    yield


app = FastAPI(
    title="Neem",
    version=__version__,
    summary="Heat twins for Delhi schoolyards",
    lifespan=lifespan,
)
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
    # Structural limits only; how much a caller may ask for is Cedar's decision.
    trees: list[TreeIn] = Field(default_factory=list, max_length=1000)
    sails: list[SailIn] = Field(default_factory=list, max_length=200)


class ApproveIn(BaseModel):
    job_id: str = Field(pattern=r"^[0-9a-f]{16}$")


recent_jobs = RecentJobs()


def identity(authorization: Annotated[str | None, Header()] = None) -> Identity:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    return identity_from_token(token, settings().dev_tokens)


Who = Annotated[Identity, Depends(identity)]


def require(decision: Decision, what: str) -> None:
    if not decision.allowed:
        raise HTTPException(403, {"detail": f"not allowed to {what}", "policy": decision.reasons})


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


@app.get("/whoami")
def whoami(who: Who) -> dict[str, Any]:
    return {"user": who.user_id, "role": who.role, "schools": list(who.schools)}


@app.post("/schools/{school_id}/designs", status_code=202)
def submit_design(school_id: str, design: DesignIn, who: Who) -> dict[str, str]:
    day = settings().day
    if not read_model.has_twin(school_id, day):
        raise HTTPException(404, f"no twin for {school_id} on {day}")
    ctx = {
        "trees": len(design.trees),
        "sails": len(design.sails),
        "recent_jobs": recent_jobs.count(who.user_id),
    }
    require(check(who, "VerifyDesign", school_id, ctx), "verify this design")
    store, queue = backends()
    job = new_job(school_id, design.model_dump() | {"day": day, "by": who.user_id})
    store.put(job)
    recent_jobs.record(who.user_id)
    queue.submit(job)
    return {"job_id": job["job_id"], "state": job["state"]}


@app.post("/schools/{school_id}/approve")
def approve(school_id: str, body: ApproveIn, who: Who) -> dict[str, Any]:
    found = backends()[0].get(body.job_id)
    if found is None or found["school_id"] != school_id:
        raise HTTPException(404, f"no design {body.job_id} for {school_id}")
    verified = found["state"] == "done"
    require(check(who, "ApproveDesign", school_id, {"verified": verified}), "approve this plan")
    record = {
        "school_id": school_id,
        "job_id": body.job_id,
        "approved_by": who.user_id,
        "design": found["design"],
        "result": found.get("result"),
    }
    out = lake.path("approved", f"{school_id}.json")
    out.write_text(json.dumps(record))
    lake.upload(out)
    return record


@app.get("/schools/{school_id}/approved")
def approved(school_id: str) -> dict[str, Any]:
    path = lake.ROOT / "approved" / f"{school_id}.json"
    if not path.exists():
        raise HTTPException(404, f"no approved plan for {school_id}")
    return json.loads(path.read_text())


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
