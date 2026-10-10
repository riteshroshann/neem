# 8. Cedar for authorization

Date: 2026-10-10
Status: accepted

## Context

Most of Neem is public: anyone may see how hot a schoolyard is and try designs in the browser. Two things are not free: physics verification costs seconds of GPU or a minute of Lambda per run, and approving a plan changes a school's record. Rules like "only this school's planner approves, and only verified plans" tend to rot when they live as `if` statements across handlers.

## Decision

Express the rules as Cedar policies (`packages/neem-api/src/neem_api/policies/neem.cedar`) validated against a schema, and evaluate them with `cedarpy` at the two costly endpoints. Context carries the facts a rule needs (tree and sail counts, jobs in the last hour, whether the run is verified). Identity comes from the auth layer: a server-side token table locally, Cognito claims on AWS. Callers can never claim a role.

## Consequences

- The policy file is the single place to read who may do what; tests exercise it directly and through HTTP.
- A `forbid` makes "never approve an unverified plan" hold even for administrators.
- The per-identity job count is in process memory; on AWS it would move to DynamoDB with a TTL.
