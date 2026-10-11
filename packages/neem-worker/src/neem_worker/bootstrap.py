"""Create the jobs table, the queue and the lake bucket, and seed the lake. Idempotent.

Used by the local stack (LocalStack) and before `sam local`. Seeding uploads the parts of the
local lake the API, worker and rank Lambdas read, so they find on emulated S3 exactly what
Lambda would.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import boto3

from neem_api.settings import settings

SEED_PREFIXES = ("scenes", "runs", "rank", "raw/met", "raw/osm", "raw/overture", "plans")
DEMO_JOB = "demo0000000000ab"


def _client(name: str) -> Any:
    s = settings()
    return boto3.client(name, region_name=s.aws_region, endpoint_url=s.aws_endpoint_url)


def tables_and_queues() -> None:
    s = settings()
    ddb = _client("dynamodb")
    if s.jobs_table not in ddb.list_tables()["TableNames"]:
        ddb.create_table(
            TableName=s.jobs_table,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    sqs = _client("sqs")
    dlq = sqs.create_queue(QueueName="neem-jobs-dlq")["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    sqs.create_queue(
        QueueName="neem-jobs",
        Attributes={
            "VisibilityTimeout": "360",
            "RedrivePolicy": f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}',
        },
    )
    print(f"bootstrap: table {s.jobs_table} and queue neem-jobs ready")


def seed_lake(src: Path) -> None:
    bucket = os.environ.get("NEEM_LAKE_BUCKET")
    if not bucket:
        return
    s3 = _client("s3")
    if bucket not in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
        s3.create_bucket(Bucket=bucket)
    n = 0
    for prefix in SEED_PREFIXES:
        root = src / prefix
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if f.is_file():
                s3.upload_file(str(f), bucket, f.relative_to(src).as_posix())
                n += 1
    print(f"bootstrap: seeded {n} lake files into s3://{bucket}")


def demo_job() -> None:
    """A queued design job for `sam local invoke WorkerFunction -e infra/events/sqs-job.json`."""
    import json

    from neem_api.jobs import DynamoJobStore, new_job

    plan = Path(os.environ.get("NEEM_LAKE_SRC", "data/lake")) / "plans" / "osm-w1321574340.json"
    design = json.loads(plan.read_text())["design"] if plan.exists() else {"trees": [], "sails": []}
    job = new_job("osm-w1321574340", design | {"day": settings().day, "by": "bootstrap"})
    job["job_id"] = DEMO_JOB
    DynamoJobStore(settings()).put(job)
    print(f"bootstrap: queued demo job {DEMO_JOB} with {len(design['trees'])} trees")


def main() -> None:
    tables_and_queues()
    seed_lake(Path(os.environ.get("NEEM_LAKE_SRC", "/lake")))
    if "--demo-job" in sys.argv:
        demo_job()


if __name__ == "__main__":
    main()
