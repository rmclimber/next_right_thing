# Content Items pagination

Status: original pagination integrated on main as `2498a3e`; deployed per user
on 2026-11-24. Compact controls/page-size follow-up authorized on 2026-11-24
is implemented locally on main, uncommitted and not deployed.
See [implementation report](implementation-report.md) for verification and remaining acceptance.

## Outcome and independence

Users can browse large Content Item collections in pages of 50 by default instead of
loading the whole collection. Existing article and podcast presentation remains.
The Item API/repository use Aurora through the existing database connection;
they do not use semantic scoring, embeddings, Bedrock or the refresh worker.
Semantic relevance is deployed but not operational due to AWS throttling,
according to the user on 2026-11-20. Troubleshooting that is outside this slice.

## Scope and implementation plan

1. Evolve the existing Item repository and GET handler with bounded, filtered
   keyset queries and validated cursor/query parameters.
2. Evolve the existing frontend Item API client and page with server filters,
   Next/Previous controls and honest page counts.
3. Add behavioral API/PostgreSQL/UI coverage and update the root API contract.

Do not add a new service, package, library, domain entity or infrastructure.
No migration is expected: `20260914_0004` already indexes user/discovery time.
Inspect query behavior; propose and justify any necessary migration rather than
silently expanding scope. Major architectural changes require an ADR and approval.

## API contract

`GET /content-items` retains Cognito ownership from JWT `sub` and all current
Content Item fields. The collection itself becomes paginated by default.

| Query | Omitted default | Valid input |
| --- | --- | --- |
| `limit` | `50` | Decimal integer 1–100 |
| `filter` | `all` | `all`, `snoozed`, `completed`, `archived` |
| `cursor` | First page | Nonempty opaque continuation token from this endpoint |

Response: `{ "content_items": [...], "next_cursor": "..." }`; `next_cursor`
is explicitly `null` on a final or empty page. There is no total-count query. The UI offers 10, 25, 50 or 100 items per page
(default 50) using this existing limit contract. An explicit empty query value is
invalid rather than an omitted default. Invalid limit/filter/cursor returns
`400` with a safe message before querying the repository; unauthenticated
requests remain `401`. Unexpected database failures remain generic `500`.

Ordering stays `discovered_at DESC, created_at DESC, id DESC`. Use strict tuple
comparison against the last returned row and SQL `LIMIT limit + 1` to discover
whether another page exists; do not use OFFSET or fetch all rows then slice.
Build the next cursor from the last returned row, not the lookahead row.

Use a small versioned base64url JSON cursor containing position timestamps, UUID
and filter. Treat it as untrusted input: validate version/shape, timezone-aware
timestamps without losing precision, UUID and matching filter, and cap token
input length (2,048 characters is sufficient). Use only parameterized SQL.
It is a position token, not an authorization credential; no signing secret,
database state, user ID, access token or new dependency is needed. Replayed or
modified cursors must never broaden the authenticated SQL ownership scope.

Apply these existing filter meanings in SQL **before** the limit:

- `all`: every owned item, including completed, archived and snoozed items.
- `snoozed`: active state and `snoozed_until` strictly later than database NOW().
- `completed` / `archived`: that current state, respectively.

Missing state rows remain active with null state timestamps. Expired snoozes
are absent from Snoozed but remain in All. Keep the owned Content Source join
and user-scoped state join. Cursor filter mismatch is `400`; changing filters
starts a fresh traversal. A valid position need not refer to a still-existing row.

## UI behavior

- Initial load requests All, limit 50, no cursor. Filters make API requests;
  remove collection filtering in the browser as the source of filter correctness.
- Compact chevron buttons expose accessible Next/Previous names and hover labels.
  Next uses `next_cursor`. Previous uses a small in-memory history of request
  cursors; first-page Previous and final-page Next are disabled. No last-page
  jump, arbitrary page jump or browser-history integration is required.
- Changing filter or page size resets cursor history/page number and starts on page
  one. Size changes retain the selected filter; filter changes retain the size.
  Page size is local state and resets to 50 on reload.
  Cancel/ignore stale responses so rapid navigation/filter changes cannot replace
  the current page with an older result. Disable duplicate navigation while loading.
- Provide loading/error/retry states. A failed navigation must be retryable and
  must not corrupt cursor history or advance a successful-page indicator.
- Say e.g. “Showing 50 items · Page 1”, not “50 total”. Empty/final/small pages
  and a first page whose requested filter has no matches remain understandable.
- Preserve summaries, sources, timestamps, state labels, known/unknown episode
  durations, external links and existing authentication/error behavior.

For a fixed dataset traversal has no duplicates or omissions, including timestamp
ties. There is no cross-request snapshot guarantee: new items above the current
position appear after restarting; deletions, disposition changes and snooze expiry
can change later or revisited pages. Document this rather than adding snapshots.

## Compatibility, boundaries and rollout

Keep the existing `content_items` envelope and per-item fields; add `next_cursor`.
Legacy clients will receive only the first 50 by default until refreshed. Deploy
the Item API before the new frontend, then refresh existing browser tabs. A new
client must not silently accept an old unbounded response as paginated: handle
missing/invalid pagination metadata with a clear retry/update error.

Do not change the Recommendation Repository's independent latest-50 pool,
eligibility, soft duration scoring, Goal attribution, semantic configuration,
embedding refresh, podcast ingestion, shared database helpers or dispositions.
Bookmarks, device handoff and manual Goal links are outside scope.

Implementation/tests are independent of working semantic relevance. Release is
still coordinated: the existing workflow deploys ingestion before API/frontend,
so a failed shared deployment step can block publishing this feature. Do not
change that workflow or embedding settings to bypass another slice's problem.
The embedding concurrency fix is integrated as `351d01b`. No additional release
or commit/push is authorized by the local 2026-11-24 UI follow-up.
The original implementation prompt is historical; its feature worktree/branch
were archived/retired during cleanup. Current work is in the primary main checkout.

See [test plan](test-plan.md) and [implementation prompt](implementation-prompt.md).
