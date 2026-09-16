# Content Item Ingestion Contract

The `nrt-<environment>-normalized-content-items` SQS queue accepts one JSON
object per message. The RSS Fetch Lambda is its current producer. Every 15
minutes, EventBridge invokes the VPC-attached Source Dispatch Lambda, which
queries active RSS Content Sources and sends one job per source to
`nrt-<environment>-rss-fetch-jobs`. The non-VPC RSS Fetch Lambda retrieves and
normalizes RSS/Atom entries, then sends them to this queue.

```json
{
  "user_id": "cognito-sub",
  "content_source_id": "550e8400-e29b-41d4-a716-446655440000",
  "external_id": "feed-guid-or-atom-id",
  "title": "Example title",
  "url": "https://example.com/post",
  "summary": "Optional summary",
  "published_at": "2026-09-15T12:00:00Z",
  "discovered_at": "2026-09-15T13:00:00Z"
}
```

Required fields are `user_id`, `content_source_id`, `external_id`, `title`,
`url`, and `discovered_at`. `summary` and `published_at` may be omitted or
`null`. Timestamps must be timezone-aware ISO 8601 values. The message must not
include database-generated IDs, producer-owned created/updated timestamps,
recommendation metadata, Topics, or embeddings.

The Content Item Writer generates `id`, `created_at`, and `updated_at`. It
inserts idempotently by `(content_source_id, external_id)` and verifies that the
referenced Content Source belongs to `user_id` before inserting.

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
