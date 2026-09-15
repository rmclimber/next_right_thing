# Content Item Ingestion Contract

The `nrt-<environment>-normalized-content-items` SQS queue accepts one JSON
object per message. Future RSS/Atom fetching and source-dispatch components are
the producers; they are not part of the current implementation.

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
