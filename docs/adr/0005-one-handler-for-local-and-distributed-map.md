# 5. One pure handler for the local pool and the Distributed Map

Date: 2026-10-10
Status: accepted

## Context

The city ranking maps one computation over thousands of schools. Locally we want a process pool; in AWS, a Step Functions Distributed Map over Lambda.

## Decision

Write `rank_one(school_id, settings) -> RankRow` as a pure function of lake inputs. An `Executor` protocol has two implementations: `LocalPoolExecutor` and `DistributedMapExecutor` (which writes an item manifest and starts the state machine). The Lambda entry point is a two-line wrapper around `rank_one`.

## Consequences

- The function we unit-test is byte-for-byte the function AWS runs.
- Retries, partial failure and result collection are the executor's job, not the handler's; failed items are recorded with their error and the ranking marks them missing rather than dropping them.
