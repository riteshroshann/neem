# 10. LocalStack and SAM CLI for the serverless stack, locally

Date: 2026-10-10
Status: accepted (supersedes the moto part of ADR 0004 for the running stack)

## Context

The deployed shape is serverless: an API Lambda behind API Gateway, a worker Lambda on SQS, a Step Functions Distributed Map for the city ranking, DynamoDB and S3. We want to run that shape on the laptop, with no AWS account. LocalStack's current image (2026.x) refuses to start without an account token.

## Decision

Describe the deployment once in `infra/template.yaml` (SAM). Build the Lambda image with `sam build` and run functions with `sam local invoke` and `sam local start-api`. Pin LocalStack to 4.14, the last open-source release, for S3, SQS, DynamoDB and Step Functions. Seed the lake into LocalStack's S3 so Lambda code reads the lake exactly as it would on AWS. Keep moto for in-process unit tests, where it is faster.

## Consequences

- The same container image runs under docker compose, `sam local` and, later, real Lambda.
- Running through the stack found two bugs moto had not: DynamoDB rejects float attributes (the job store now writes keys and a JSON document only), and SAM's emulator layer needs a root build user (the image no longer sets USER; compose applies it instead).
- Pinning an old LocalStack means no new emulator fixes; acceptable for a hackathon window.
