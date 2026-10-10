"""HTTP-level checks that Cedar actually guards the endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from neem_api import main
from neem_api.authz import RecentJobs
from neem_api.jobs import FileJobStore, Job
from neem_api.settings import Settings

KV = "osm-w1321574340"
TOKENS = {"t-kv": {"user": "principal@kv25", "role": "planner", "schools": [KV]}}


class NullQueue:
    def __init__(self) -> None:
        self.jobs: list[Job] = []

    def submit(self, job: Job) -> None:
        self.jobs.append(job)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, FileJobStore]:
    store = FileJobStore(tmp_path / "jobs")
    monkeypatch.setattr(main, "backends", lambda: (store, NullQueue()))
    monkeypatch.setattr(main, "settings", lambda: Settings(dev_tokens=TOKENS))
    monkeypatch.setattr("neem_api.read_model.has_twin", lambda *_: True)
    monkeypatch.setattr("neem_data.lake.ROOT", tmp_path)
    monkeypatch.setattr(main, "recent_jobs", RecentJobs())
    return TestClient(main.app), store


def _design(n: int) -> dict[str, Any]:
    return {"trees": [{"x": 700000 + i, "y": 3180000} for i in range(n)], "sails": []}


def test_reasonable_design_is_queued(client: tuple[TestClient, FileJobStore]) -> None:
    c, _ = client
    r = c.post(f"/schools/{KV}/designs", json=_design(10))
    assert r.status_code == 202


def test_oversized_design_is_refused_by_policy(client: tuple[TestClient, FileJobStore]) -> None:
    c, _ = client
    r = c.post(f"/schools/{KV}/designs", json=_design(250))
    assert r.status_code == 403


def test_approval_needs_the_schools_planner_and_a_verified_run(
    client: tuple[TestClient, FileJobStore],
) -> None:
    c, store = client
    job_id = c.post(f"/schools/{KV}/designs", json=_design(3)).json()["job_id"]
    assert c.post(f"/schools/{KV}/approve", json={"job_id": job_id}).status_code == 403
    planner = {"Authorization": "Bearer t-kv"}
    # not verified yet: even the right planner is refused
    assert (
        c.post(f"/schools/{KV}/approve", json={"job_id": job_id}, headers=planner).status_code
        == 403
    )
    store.transition(job_id, "queued", {"state": "running"})
    store.transition(job_id, "running", {"state": "done", "result": {"ok": True}})
    r = c.post(f"/schools/{KV}/approve", json={"job_id": job_id}, headers=planner)
    assert r.status_code == 200 and r.json()["approved_by"] == "principal@kv25"
    assert c.get(f"/schools/{KV}/approved").json()["job_id"] == job_id
