# API

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
