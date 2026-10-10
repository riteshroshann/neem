"""Neem worker: consume design jobs from SQS and verify them with SOLWEIG.

Two entry points, one code path: `run()` long-polls SQS (local stack, ECS), and `handler()`
is the Lambda entry for an SQS event source mapping.
"""

from __future__ import annotations

import json
import logging
import signal
from typing import Any

import boto3

from neem_api.jobs import DynamoJobStore, run_job
from neem_api.settings import settings
from neem_data import lake

log = logging.getLogger("neem.worker")


def _job_id(body: str) -> str:
    return str(json.loads(body)["job_id"])


_synced = False


def handler(event: dict[str, Any], _context: object) -> dict[str, Any]:
    """Lambda entry. Failed records are reported back so only they are retried."""
    global _synced
    if not _synced:  # cold start: scenes, base runs and weather from the lake bucket
        lake.sync_from_s3(["scenes/", "runs/", "raw/met/"])
        _synced = True
    store = DynamoJobStore(settings())
    failures = []
    for record in event.get("Records", []):
        try:
            run_job(store, _job_id(record["body"]))
        except Exception:
            log.exception("job failed")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    s = settings()
    if not s.jobs_queue_url:
        raise SystemExit("NEEM_JOBS_QUEUE_URL is not set")
    sqs = boto3.client("sqs", region_name=s.aws_region, endpoint_url=s.aws_endpoint_url)
    store = DynamoJobStore(s)
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("polling %s", s.jobs_queue_url)
    while not stopping:
        resp = sqs.receive_message(
            QueueUrl=s.jobs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=300,
        )
        for msg in resp.get("Messages", []):
            job_id = _job_id(msg["Body"])
            log.info("job %s", job_id)
            run_job(store, job_id)
            # run_job records failures on the job itself, so the message is always done
            sqs.delete_message(QueueUrl=s.jobs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
