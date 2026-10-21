# ADR-0006: RSS Fetch Uses RDS Data API for Content Source Health

## Status

Accepted

## Context

RSS Fetch must reach public RSS and Atom feeds, so it intentionally runs outside
the VPC. Content Source lifecycle state shows configuration intent, but it does
not show whether the most recent feed fetch and parse actually worked.

Moving RSS Fetch into the VPC would require public egress infrastructure, while
adding a queue or status-writer Lambda would add complexity without improving
content ingestion. The existing Aurora Data API is already enabled for Source
Dispatch.

## Decision

Add `last_fetch_status`, `last_fetch_attempt_at`, `last_fetch_success_at`, and
`last_fetch_error` to `content_sources`. RSS Fetch performs one small Data API
`UPDATE`, scoped by both Content Source ID and User ID, after every fetch/parse
outcome. Its role receives only RDS Data API statement permission and access to
the existing RDS-managed secret for Data API authorization; it never retrieves
the database password.

Health persistence is telemetry. A health-update failure is logged clearly but
does not alter SQS acknowledgement semantics or retry successfully published
normalized items. Source lifecycle and feed health remain separate.

## Consequences

- Source Dispatch uses Data API for source discovery; RSS Fetch uses it for a
  lightweight source-health update; application APIs and Writer stay on psycopg
  over the VPC.
- No NAT Gateway, VPC endpoint, queue, Lambda, database, cache, or other
  fixed-cost infrastructure is added.
- The UI can distinguish never checked, healthy, invalid feed, and fetch error
  without exposing raw ingestion details.
