"""Job ports against moto: the same boto3 calls the deployed system makes."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from moto import mock_aws

from neem_api import jobs
from neem_api.jobs import (
    DynamoJobStore,
    FileJobStore,
    JobStore,
    SqsJobQueue,
    StaleTransitionError,
    new_job,
    run_job,
)
from neem_api.settings import Settings

QUEUE = "https://sqs.ap-south-1.amazonaws.com/123456789012/neem-jobs"


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    for k, v in {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "ap-south-1",
    }.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        s = Settings(jobs="aws", jobs_queue_url=QUEUE)
        monkeypatch.setattr("neem_worker.bootstrap.settings", lambda: s)
        from neem_worker.bootstrap import main

        main()
        yield s


@pytest.fixture(params=["file", "dynamo"])
def store(request: pytest.FixtureRequest, tmp_path: Path, aws: Settings) -> JobStore:
    return FileJobStore(tmp_path) if request.param == "file" else DynamoJobStore(aws)


def test_transitions_are_conditional(store: JobStore) -> None:
    job = new_job("osm-w1", {"trees": [], "day": "2026-04-27"})
    store.put(job)
    store.transition(job["job_id"], "queued", {"state": "running"})
    with pytest.raises(StaleTransitionError):
        store.transition(job["job_id"], "queued", {"state": "running"})
    done = store.transition(job["job_id"], "running", {"state": "done", "result": {"ok": 1}})
    assert store.get(job["job_id"]) == done


def test_redelivered_job_runs_once(store: JobStore, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_verify(school_id: str, day: str, items: Any) -> dict[str, Any]:
        calls.append(school_id)
        return {"school_id": school_id, "day": day, "n": len(items)}

    monkeypatch.setattr("neem_data.designs.verify", fake_verify)
    job = new_job("osm-w1", {"trees": [{"x": 1, "y": 2}], "sails": [], "day": "2026-04-27"})
    store.put(job)
    run_job(store, job["job_id"])
    run_job(store, job["job_id"])  # SQS delivers at least once
    final = store.get(job["job_id"])
    assert calls == ["osm-w1"]
    assert final is not None and final["state"] == "done" and final["result"]["n"] == 1


def test_failure_is_recorded_on_the_job(store: JobStore, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any) -> dict[str, Any]:
        raise RuntimeError("solweig fell over")

    monkeypatch.setattr("neem_data.designs.verify", boom)
    job = new_job("osm-w1", {"day": "2026-04-27"})
    store.put(job)
    run_job(store, job["job_id"])
    final = store.get(job["job_id"])
    assert final is not None and final["state"] == "failed" and "fell over" in final["error"]


def test_queue_carries_only_the_job_id(aws: Settings) -> None:
    import boto3

    job = new_job("osm-w1", {"day": "2026-04-27"})
    SqsJobQueue(aws).submit(job)
    msgs = boto3.client("sqs", region_name="ap-south-1").receive_message(QueueUrl=QUEUE)
    assert json.loads(msgs["Messages"][0]["Body"]) == {"job_id": job["job_id"]}
    assert jobs.now()  # clock is wired
