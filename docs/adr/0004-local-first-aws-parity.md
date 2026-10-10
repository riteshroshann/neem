# 4. Local first, with AWS parity through ports and adapters

Date: 2026-10-10
Status: accepted

## Context

All development and testing happens on a laptop before an AWS account exists. The deployed system uses S3, SQS, DynamoDB, Lambda and Step Functions.

## Decision

Code talks to three ports: `BlobStore`, `JobQueue` and `JobStore`. The boto3 adapters take an endpoint URL. Locally that is moto server in Docker; in unit tests it is moto in-process; in AWS it is unset. Containers built for the local stack are the same images deployed to Lambda.

## Consequences

- Integration tests exercise real boto3 calls against an emulator, so wiring bugs show up locally.
- Emulators differ from AWS in edge cases (IAM, eventual consistency). We accept that and keep a short post-deploy smoke test.
- We chose moto over LocalStack because it is Apache-2.0, needs no account or token, and doubles as an in-process test fixture.
