# Content Item Ingestion Contract

The `nrt-<environment>-normalized-content-items` SQS queue accepts one JSON
object per message. The RSS Fetch Lambda is its current producer. Every 120
minutes, EventBridge invokes the non-VPC Source Dispatch Lambda, which uses the
RDS Data API to query active RSS Content Sources and sends one job per source to
`nrt-<environment>-rss-fetch-jobs`. The non-VPC RSS Fetch Lambda retrieves and
normalizes RSS/Atom entries, then sends them to this queue.

Extended message example (producers may omit the two new optional fields):

```json
{
  "user_id": "cognito-sub",
  "content_source_id": "550e8400-e29b-41d4-a716-446655440000",
  "external_id": "feed-guid-or-atom-id",
  "content_type": "article",
  "duration_minutes": null,
  "title": "Example title",
  "url": "https://example.com/post",
  "summary": "Optional summary",
  "published_at": "2026-09-15T12:00:00Z",
  "discovered_at": "2026-09-15T13:00:00Z"
}
```

Required fields are `user_id`, `content_source_id`, `external_id`, `title`,
`url`, and `discovered_at`. `summary` and `published_at` may be omitted or
`null`. For compatibility with older producers, an omitted `content_type`
defaults to `article`; an omitted or explicitly null `duration_minutes` defaults
to `null`. Explicit `content_type` must be one of `article`, `podcast_episode`,
`video`, `research_article`, or `book`; null, unknown, or non-string types are
rejected. Known duration must be a positive JSON integer within PostgreSQL
integer bounds (1 through 2,147,483,647); booleans, fractions, numeric strings,
zero, and negative values are rejected. Invalid values follow the existing
permanent-message acknowledgement policy.

RSS Fetch retains its existing RSS/Atom message format and omits
`content_type` and `duration_minutes`. Writer supplies `article` and `null`
through the defaults above. Keeping the producer payload unchanged lets Fetch
and Writer deploy in either order during this milestone. Neither Fetch nor
Writer infers type or known duration. `ContentSource.source_type` describes how/
where content is obtained; `ContentItem.content_type` describes what the item
is. These are independent, so a later RSS producer may emit podcast episodes.
Known duration is durable source metadata; the summary-based Candidate Action
estimate is ephemeral and is never written back into Content Items.

Timestamps must be timezone-aware ISO 8601 values. The message must not
include database-generated IDs, producer-owned created/updated timestamps,
recommendation metadata, Topics, or embeddings.

The Content Item Writer generates `id`, `created_at`, and `updated_at`. It
inserts idempotently by `(content_source_id, external_id)` and verifies that the
referenced Content Source belongs to `user_id` before inserting. Duplicate
messages do not update existing item metadata, including type or duration.

Deploy migration `20261116_0008` before updated writers or API readers. It
backfills all existing items to non-null `article`, leaves duration unknown, and
retains a database `article` default so the old Writer remains compatible. Deploy
the frontend accepting both action names before enabling the new recommendation
response using a separate frontend compatibility release. Already-open browser
tabs must refresh to load that client. Fetch retains the existing payload, so
Fetch and Writer need no relative deployment ordering in this milestone. Future
producers that explicitly send the new fields must follow deployment of the
extended Writer, since old Writer versions reject unknown message fields. The
updated Writer accepts old queued messages throughout this rollout. No
Recommendation Event history is rewritten.

Malformed messages and ownership-invalid messages are logged safely and
acknowledged. They do not currently have a dead-letter queue. Transient database
or secret-retrieval failures are reported as partial batch failures and retried
by SQS/Lambda.

The fetch-jobs queue and normalized queue intentionally have no DLQ in this
milestone. Permanent malformed jobs and non-429 HTTP 4xx feed responses are
logged and acknowledged. Network failures, HTTP 429/5xx responses, and failures
to publish normalized items are retried per SQS record. Repeated feed entries
are expected on every poll: Writer uniqueness on `(content_source_id,
external_id)` is the idempotency boundary. No feed-state, ETag, or conditional
fetch optimization exists yet.

## Source health

RSS Fetch records lightweight operational health on the owned Content Source
through the Aurora RDS Data API. It updates by both `content_source_id` and
`user_id`; a missing source is logged and is never recreated. This is a targeted
non-VPC database operation, like Source Dispatch's source discovery. The
application APIs and Content Item Writer continue to use psycopg through the
VPC.

`healthy` means an HTTP fetch and usable RSS/Atom parse succeeded, including a
valid feed with zero entries. `invalid_feed` means the HTTP request succeeded
but the body could not be parsed as RSS/Atom. `fetch_error` covers network,
timeout, and HTTP failures. Each result records an attempt time; only `healthy`
updates the latest-success time, and it clears the previous error.

Health persistence is secondary telemetry. A Data API failure is logged as an
operational error but does not change SQS acknowledgement or retry semantics:
it cannot cause already-published normalized items to be re-published, and it
does not turn a permanent 4xx feed response into a retry.

## Manual health refresh

After deployment, an operator can manually invoke Source Dispatch from their
normal PowerShell session, replacing `dev` with the deployed environment:

```powershell
aws lambda invoke --function-name nrt-dev-source-dispatch --cli-binary-format raw-in-base64-out --payload '{}' source-dispatch-response.json
Get-Content -Raw .\source-dispatch-response.json
```

This emits one fetch job for each active RSS Content Source. The RSS Fetch
Lambda then updates its health on the next queue delivery; the response file
should show a successful dispatch result.
