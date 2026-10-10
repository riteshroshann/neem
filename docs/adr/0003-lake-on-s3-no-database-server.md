# 3. A lake on S3, queried in place; no database server

Date: 2026-10-10
Status: accepted

## Context

Our data is mostly immutable and analytical: open datasets, rasters, model runs, a ranking table rebuilt in batch. Writes are rare and append-only, except job state.

## Decision

Store everything as files on S3: GeoParquet, Cloud-Optimised GeoTIFF, compressed NumPy scenes and JSON manifests. Query tables with DuckDB directly from S3. Keep only job state in DynamoDB, where we need conditional writes.

## Consequences

- No database to provision, migrate or keep warm; the API is stateless and starts cold quickly.
- The same layout works on local disk, on moto, and on S3.
- Point lookups on large tables are slower than a database would give; our tables are small enough (thousands of schools) that this does not matter.
