"""Create the jobs table and queue if they do not exist. Idempotent; used by the local stack."""

from __future__ import annotations

from typing import Any

import boto3

from neem_api.settings import settings


def main() -> None:
    s = settings()
    ddb: Any = boto3.client("dynamodb", region_name=s.aws_region, endpoint_url=s.aws_endpoint_url)
    if s.jobs_table not in ddb.list_tables()["TableNames"]:
        ddb.create_table(
            TableName=s.jobs_table,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    sqs: Any = boto3.client("sqs", region_name=s.aws_region, endpoint_url=s.aws_endpoint_url)
    dlq = sqs.create_queue(QueueName="neem-jobs-dlq")["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    sqs.create_queue(
        QueueName="neem-jobs",
        Attributes={
            "VisibilityTimeout": "300",
            "RedrivePolicy": f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}',
        },
    )
    print(f"bootstrap: table {s.jobs_table} and queue neem-jobs ready")


if __name__ == "__main__":
    main()
