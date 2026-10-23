# API

## POST /content-items/{id}/actions

Requires the standard authenticated Cognito access token. The Content Item is
scoped to the authenticated JWT `sub`; inaccessible and nonexistent items both
return `404`. The client cannot provide a `user_id`.

Request body:

```json
{
  "action": "complete",
  "recommendation_event_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

`action` is required and must be `snooze`, `complete`, or `archive`.
`recommendation_event_id` is optional; when supplied it must belong to the user
and reference the same Content Item, otherwise the request returns `400`.
Snooze makes the item temporarily ineligible for exactly 24 hours. Complete and
archive make it ineligible permanently. A successful request atomically updates
the current state and creates an immutable User Action Event.

Success response: `200 OK`

```json
{
  "content_item_state": {
    "content_item_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "completed",
    "snoozed_until": null,
    "completed_at": "2026-10-16T12:00:00+00:00"
  }
}
```

Malformed requests and unsupported actions return `400`; internal failures
return a generic `500 Internal Server Error`.

## GET /recommendations/next

Requires a valid Cognito access token in the `Authorization: Bearer <token>`
header. The token must include the `aws.cognito.signin.user.admin` scope.
Ownership is derived exclusively from
`requestContext.authorizer.jwt.claims.sub`; callers cannot supply a `user_id`.

Required query parameter:

- `available_minutes`: integer from `1` through `240`, inclusive.

Success response: `200 OK`

```json
{
  "recommendation": {
    "recommendation_event_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_type": "read_content_item",
    "content_item": {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Example title",
      "url": "https://example.com/article",
      "summary": "Optional summary",
      "published_at": "2026-10-02T12:00:00+00:00",
      "discovered_at": "2026-10-02T13:00:00+00:00",
      "content_source": {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Example feed",
        "url": "https://example.com/feed.xml"
      }
    },
    "estimated_duration_minutes": 5,
    "reason": "Recent item that fits your 20-minute window."
  }
}
```

When the authenticated user has no Content Items, the endpoint returns `200 OK`
with `{ "recommendation": null }` and does not create a Recommendation Event.
`content_source` identifies the owned Content Source that produced the recommended
Content Item and never exposes its owner.
Invalid `available_minutes` values return `400 Bad Request` with a JSON
`message`. Internal failures return a generic `500 Internal Server Error`.

## GET /content-items

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Returns Content Items owned by the authenticated Cognito user. Ownership is
derived exclusively from `requestContext.authorizer.jwt.claims.sub`; the
response never exposes `user_id`. Results are ordered newest-first by
`discovered_at`, then `created_at`, then `id` for deterministic ordering.

Success response: `200 OK`

```json
{
  "content_items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "content_source_id": "550e8400-e29b-41d4-a716-446655440001",
      "external_id": "feed-guid-or-atom-id",
      "title": "Example title",
      "url": "https://example.com/post",
      "summary": "Optional summary",
      "published_at": "2026-09-15T12:00:00+00:00",
      "discovered_at": "2026-09-15T13:00:00+00:00",
      "created_at": "2026-09-15T13:00:01+00:00",
      "updated_at": "2026-09-15T13:00:01+00:00",
      "content_source": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Example feed",
        "url": "https://example.com/feed.xml"
      },
      "status": "active",
      "snoozed_until": null,
      "completed_at": null
    }
  ]
}
```

`summary` and `published_at` may be `null`. `content_source` is the owned source
that produced the item and never exposes its owner. `status` is `active`, `completed`,
or `archived`; `snoozed_until` and `completed_at` may be `null`. Items without
a Content Item User State row are returned as `active` with both timestamps
`null`. An item is currently snoozed when its status is `active` and its
`snoozed_until` is in the future. The endpoint exposes only current
disposition, not User Action Event history. An authenticated user with no
Content Items receives `{ "content_items": [] }` with `200 OK`. Internal
failures return a generic `500 Internal Server Error` response.

## GET /me

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Response:

```json
{
  "sub": "cognito-user-sub"
}
```

## POST /goals

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Creates a Goal owned by the authenticated Cognito user. Ownership is derived
from `requestContext.authorizer.jwt.claims.sub`; callers cannot provide or
override `user_id`.

Request:

```json
{
  "title": "Learn Bayesian statistics",
  "description": "Work through a practical text",
  "target_date": "2027-03-31"
}
```

Required fields:

- `title`: non-empty string after trimming

Optional fields:

- `description`: string or `null`
- `target_date`: ISO calendar date in `YYYY-MM-DD` format or `null`

The request must be a valid JSON object. The following fields are rejected if
supplied by the client: `id`, `user_id`, `status`, `created_at`, `updated_at`,
and `completed_at`.

New Goals always begin with `status` set to `active`; `completed_at` is `null`.

Success response: `201 Created`

```json
{
  "id": "goal-uuid",
  "title": "Learn Bayesian statistics",
  "description": "Work through a practical text",
  "status": "active",
  "target_date": "2027-03-31",
  "created_at": "2026-08-22T12:00:00+00:00",
  "updated_at": "2026-08-22T12:00:00+00:00",
  "completed_at": null
}
```

Validation failures return `400 Bad Request` with a JSON `message`. Internal
failures return a generic `500 Internal Server Error` response.

## GET /goals

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Returns Goals owned by the authenticated Cognito user. The response never
includes Goals for another user. Results are ordered by newest creation time
first.

Success response: `200 OK`

```json
{
  "goals": [
    {
      "id": "goal-uuid",
      "title": "Learn Bayesian statistics",
      "description": null,
      "status": "active",
      "target_date": null,
      "created_at": "2026-08-22T12:00:00+00:00",
      "updated_at": "2026-08-22T12:00:00+00:00",
      "completed_at": null
    }
  ]
}
```

An authenticated user with no Goals receives:

```json
{
  "goals": []
}
```

Internal failures return a generic `500 Internal Server Error` response.

## POST /content-sources

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Creates a Content Source owned by the authenticated Cognito user. Ownership is
derived from `requestContext.authorizer.jwt.claims.sub`; callers cannot provide
or override `user_id`.

Request:

```json
{
  "name": "AWS Machine Learning Blog",
  "url": "https://example.com/feed.xml"
}
```

Required fields:

- `name`: non-empty string after trimming
- `url`: syntactically valid HTTP or HTTPS URL

The request must be a valid JSON object. The following fields are rejected if
supplied by the client: `id`, `user_id`, `source_type`, `status`, `created_at`,
and `updated_at`.

New Content Sources always begin with `source_type` set to `rss` and `status`
set to `active`. The API does not fetch or validate live RSS feed contents.

Success response: `201 Created`

```json
{
  "id": "content-source-uuid",
  "name": "AWS Machine Learning Blog",
  "source_type": "rss",
  "url": "https://example.com/feed.xml",
  "status": "active",
  "created_at": "2026-09-01T12:00:00+00:00",
  "updated_at": "2026-09-01T12:00:00+00:00",
  "last_fetch_status": null,
  "last_fetch_attempt_at": null,
  "last_fetch_success_at": null,
  "last_fetch_error": null
}
```

Validation failures return `400 Bad Request` with a JSON `message`. If the
authenticated user already has a Content Source with the same exact URL, the API
returns `409 Conflict`. Internal failures return a generic
`500 Internal Server Error` response.

## GET /content-sources

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Returns Content Sources owned by the authenticated Cognito user. The response
never includes Content Sources for another user. Results are ordered by newest
creation time first.

Success response: `200 OK`

```json
{
  "content_sources": [
    {
      "id": "content-source-uuid",
      "name": "AWS Machine Learning Blog",
      "source_type": "rss",
      "url": "https://example.com/feed.xml",
      "status": "active",
      "created_at": "2026-09-01T12:00:00+00:00",
      "updated_at": "2026-09-01T12:00:00+00:00",
      "last_fetch_status": null,
      "last_fetch_attempt_at": null,
      "last_fetch_success_at": null,
      "last_fetch_error": null
    }
  ]
}
```

An authenticated user with no Content Sources receives:

```json
{
  "content_sources": []
}
```

`last_fetch_status` is `healthy`, `invalid_feed`, `fetch_error`, or `null` when
the source has never been checked. Fetch health is separate from source
lifecycle status. Internal failures return a generic `500 Internal Server Error` response.

## PATCH /content-sources/{id}

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Updates a Content Source owned by the authenticated Cognito user. Ownership is
derived from `requestContext.authorizer.jwt.claims.sub`; callers cannot provide
or override `user_id`. The update is scoped by both the requested Content Source
`id` and the authenticated user, so nonexistent Content Sources and Content
Sources owned by other users both return `404 Not Found`.

Request:

```json
{
  "name": "AWS Machine Learning Blog",
  "url": "https://example.com/feed.xml",
  "status": "paused"
}
```

Supported fields:

- `name`: non-empty string after trimming
- `url`: syntactically valid HTTP or HTTPS URL
- `status`: one of `active`, `paused`, or `archived`

The request must be a valid JSON object with at least one supported update
field. Unsupported fields are rejected, including the system-managed fields
`id`, `user_id`, `source_type`, `created_at`, and `updated_at`.

Successful updates always set `updated_at` to the current UTC timestamp. The API
does not fetch or validate live RSS feed contents.

Success response: `200 OK`

```json
{
  "id": "content-source-uuid",
  "name": "AWS Machine Learning Blog",
  "source_type": "rss",
  "url": "https://example.com/feed.xml",
  "status": "paused",
  "created_at": "2026-09-01T12:00:00+00:00",
  "updated_at": "2026-09-01T12:30:00+00:00",
  "last_fetch_status": "healthy",
  "last_fetch_attempt_at": "2026-09-01T12:25:00+00:00",
  "last_fetch_success_at": "2026-09-01T12:25:00+00:00",
  "last_fetch_error": null
}
```

Validation failures return `400 Bad Request` with a JSON `message`.
Nonexistent or inaccessible Content Sources return `404 Not Found` with no
distinction between the two cases. If a URL change conflicts with another
Content Source owned by the same user, the API returns `409 Conflict`. Internal
failures return a generic `500 Internal Server Error` response.

## PATCH /goals/{id}

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Updates a Goal owned by the authenticated Cognito user. Ownership is derived
from `requestContext.authorizer.jwt.claims.sub`; callers cannot provide or
override `user_id`. The update is scoped by both the requested Goal `id` and
the authenticated user, so nonexistent Goals and Goals owned by other users
both return `404 Not Found`.

Request:

```json
{
  "title": "Learn Bayesian statistics",
  "description": "Finish the text and exercises",
  "target_date": "2027-03-31",
  "status": "completed"
}
```

Supported fields:

- `title`: non-empty string after trimming
- `description`: string or `null`; `null` clears the description
- `target_date`: ISO calendar date in `YYYY-MM-DD` format or `null`; `null` clears the target date
- `status`: one of `active`, `paused`, `completed`, or `archived`

The request must be a valid JSON object with at least one supported update
field. Unsupported fields are rejected, including the system-managed fields
`id`, `user_id`, `created_at`, `updated_at`, and `completed_at`.

Successful updates always set `updated_at` to the current UTC timestamp.
Completion timestamps follow the Goal lifecycle:

- transitioning to `completed` sets `completed_at` to the current UTC timestamp
- updating an already-completed Goal without changing status preserves `completed_at`
- transitioning from `completed` to a non-completed status clears `completed_at`
- transitions among non-completed statuses leave `completed_at` as `null`

Success response: `200 OK`

```json
{
  "id": "goal-uuid",
  "title": "Learn Bayesian statistics",
  "description": "Finish the text and exercises",
  "status": "completed",
  "target_date": "2027-03-31",
  "created_at": "2026-08-22T12:00:00+00:00",
  "updated_at": "2026-08-22T12:30:00+00:00",
  "completed_at": "2026-08-22T12:30:00+00:00"
}
```

Validation failures return `400 Bad Request` with a JSON `message`.
Nonexistent or inaccessible Goals return `404 Not Found` with no distinction
between the two cases. Internal failures return a generic
`500 Internal Server Error` response.
