"""Job ports and adapters (ADR 0004).

A job moves queued -> running -> done | failed. Every transition is conditional on the
current state, so a redelivered message can never run a finished job twice.
"""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import boto3

from neem_api.settings import Settings

Job = dict[str, Any]


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_job(school_id: str, design: dict[str, Any]) -> Job:
    t = now()
    return {
        "job_id": uuid.uuid4().hex[:16],
        "school_id": school_id,
        "design": design,
        "state": "queued",
        "created": t,
        "updated": t,
    }


class StaleTransitionError(Exception):
    """The job was not in the expected state; someone else moved it."""


class JobStore(Protocol):
    def put(self, job: Job) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def transition(self, job_id: str, expected: str, changes: Job) -> Job: ...


class JobQueue(Protocol):
    def submit(self, job: Job) -> None: ...


class FileJobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def put(self, job: Job) -> None:
        self._path(job["job_id"]).write_text(json.dumps(job))

    def get(self, job_id: str) -> Job | None:
        p = self._path(job_id)
        return json.loads(p.read_text()) if p.exists() else None

    def transition(self, job_id: str, expected: str, changes: Job) -> Job:
        with self._lock:
            job = self.get(job_id)
            if job is None or job["state"] != expected:
                raise StaleTransitionError(job_id)
            job |= changes | {"updated": now()}
            self.put(job)
            return job


class DynamoJobStore:
    def __init__(self, s: Settings) -> None:
        resource: Any = boto3.resource(
            "dynamodb", region_name=s.aws_region, endpoint_url=s.aws_endpoint_url
        )
        self.table = resource.Table(s.jobs_table)

    def put(self, job: Job) -> None:
        # only keys and state as attributes: DynamoDB rejects floats, and the doc is the truth
        item = {k: job[k] for k in ("job_id", "state", "school_id")}
        self.table.put_item(Item=item | {"doc": json.dumps(job)})

    def get(self, job_id: str) -> Job | None:
        item = self.table.get_item(Key={"job_id": job_id}).get("Item")
        return json.loads(str(item["doc"])) if item else None

    def transition(self, job_id: str, expected: str, changes: Job) -> Job:
        job = self.get(job_id)
        if job is None:
            raise StaleTransitionError(job_id)
        job |= changes | {"updated": now()}
        try:
            self.table.put_item(
                Item={**{k: job[k] for k in ("job_id", "state")}, "doc": json.dumps(job)},
                ConditionExpression="#s = :expected",
                ExpressionAttributeNames={"#s": "state"},
                ExpressionAttributeValues={":expected": expected},
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException as exc:
            raise StaleTransitionError(job_id) from exc
        return job


class SqsJobQueue:
    def __init__(self, s: Settings) -> None:
        if not s.jobs_queue_url:
            raise ValueError("NEEM_JOBS_QUEUE_URL is required for the aws job backend")
        self.url = s.jobs_queue_url
        self.sqs = boto3.client("sqs", region_name=s.aws_region, endpoint_url=s.aws_endpoint_url)

    def submit(self, job: Job) -> None:
        self.sqs.send_message(QueueUrl=self.url, MessageBody=json.dumps({"job_id": job["job_id"]}))


class ThreadJobQueue:
    """In-process queue for development: runs the same handler the worker runs."""

    def __init__(self, store: JobStore, workers: int = 1) -> None:
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="neem-job")

    def submit(self, job: Job) -> None:
        self.pool.submit(run_job, self.store, job["job_id"])


def run_job(store: JobStore, job_id: str) -> None:
    """Execute one design verification. Shared by ThreadJobQueue and the worker."""
    from neem_data.designs import parse, verify

    try:
        job = store.transition(job_id, "queued", {"state": "running"})
    except StaleTransitionError:
        return  # already taken or finished: at-least-once delivery, exactly-once effect
    try:
        result = verify(job["school_id"], job["design"]["day"], parse(job["design"]))
        store.transition(job_id, "running", {"state": "done", "result": result})
    except Exception as exc:
        store.transition(
            job_id, "running", {"state": "failed", "error": f"{type(exc).__name__}: {exc}"}
        )
