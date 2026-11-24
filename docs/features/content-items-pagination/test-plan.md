# Content Items pagination test plan

Status: original slice merged and deployed (user-reported 2026-11-24).
Compact controls/page-size follow-up is local and uncommitted. See the
[implementation report](implementation-report.md) for results and skipped database acceptance.
Contract: [specification](spec.md).

## API and real PostgreSQL behavior

- Given more than 100 owned articles/episodes, when listing without query
  parameters, then exactly 50 are returned in existing deterministic order,
  per-item data is unchanged, and a next cursor is present.
- Given a fixed dataset with equal discovery and creation timestamps, when
  following all cursors, then every item appears exactly once in correct UUID
  order. Include 0, 1, 49, 50, 51, 100 and 101 item boundaries; final/empty
  `next_cursor` is null, without an extra empty request for exactly 50 items.
- Given items owned by another user or an ownership-invalid source join, when
  querying with any cursor, then none of their rows or state is disclosed.
  Include replay/modification of another user's cursor position.
- Given mixed states, including matching items beyond the first 50 unfiltered
  rows, when filtering, then matching rows fill pages across the full collection.
  Missing states stay active, future active snoozes are included in Snoozed,
  expired snoozes and snoozed timestamps on completed/archived rows are excluded.
- Given valid limits 1, 50 and 100, when listing, then the requested bound applies.
  Invalid numeric/empty/out-of-range limits, invalid filters and malformed,
  oversized, wrong-version, wrong-filter or invalid-date/UUID cursors return 400
  without a repository query. Unauthenticated requests remain 401.
- Given the cursor's boundary row is deleted, when requesting the next page,
  then its encoded position still works. Inserting a newer item must not shift
  the continuation boundary; restarting can reveal the new item.
- Given data changes/snooze expiry between requests, when revisiting pages,
  then documented current-data semantics apply without a false snapshot claim.
- Given the SQL listing path, when retrieving a page, then filtering and the
  `limit + 1` bound happen in the database, not after an unbounded fetch. Use real
  repository/API behavior checks, with focused SQL-boundary assertions where useful.
- Given semantic provider/cache availability is absent, when listing/navigating,
  then pagination still works without provider calls or embedding-table reads.
- Given database failure, when listing, then the API returns a generic 500.

Use a disposable `NRT_TEST_DATABASE_URL` with `postgresql+psycopg://...` to enable
an isolated-schema PostgreSQL integration test; follow existing migration/test
patterns and clean up that schema. Never use an application database. Skips are
not evidence of PostgreSQL correctness; report them explicitly.

## Frontend behavior

- Given page one, when its next cursor exists, then Go to page offers 1 and 2,
  with only the successful current page highlighted. Visiting page two may expose
  3, while a final page exposes no extra unknown page. No total count is implied.
- Given multiple visited pages, when jumping by number from either control bar,
  then the saved request cursor is used directly. Returning to an unchanged earlier
  page preserves later links. Changed boundaries discard downstream links, and
  filter/size changes reset numbered history. Errors remain retryable and stale
  requests cannot change the history or successful current-page indicator.

- Given top and bottom pagination controls, when navigating or changing size from
  either position, then both reflect the same state; they appear before and after
  the item list and have distinct accessible navigation labels.
- Given page one with a next cursor, when navigating Next/Previous, then the
  correct request cursor, filter and selected size are sent; at most the selected
  number of items are displayed;
  page labels are honest, and first/final controls have the correct disabled state.
- Given page two, when changing filter, then the UI requests its first page,
  clears old cursor history, and displays all matches from the server response.
- Given compact navigation controls, when using keyboard/screen-reader navigation,
  then Previous/Next have accessible names, hover labels, chevron icons and the
  existing disabled/loading behavior.
- Given page two and a selected filter, when choosing 10/25/50/100 items per page,
  then the next request uses the chosen limit and no cursor, resets to page one,
  clears history and retains the filter. Subsequent Next/Previous use that size.
- Given a size change during loading or a failed request, when an older response
  arrives or Retry is selected, then stale data is ignored and Retry uses the new
  size. Reload starts at default 50; filter changes retain the current size.
- Given overlapping requests, when an older request resolves last, then it does
  not replace the current page. Failed navigation/retry must preserve valid history.
- Given empty, partial-final or old-backend responses, when rendering, then
  empty states/counts/errors are correct and missing pagination metadata is not
  silently treated as a successfully paginated response.
- Given existing articles/episodes, when rendering any page, then source,
  summary, state, duration and Open article/Listen externally behavior remain.

## Regression and release verification

Run backend unittest discovery, all web tests, TypeScript checking and static
build using [handoff commands](implementation-prompt.md#validation). Adapt existing
API/podcast tests to the new envelope; do not weaken their behavioral assertions.
Report command, interpreter, commit, result and every skipped/blocked check.

Original deployment is user-reported; full manual acceptance remains outstanding.
After a separately approved release of the UI follow-up, also verify the size
selector and icon controls on desktop/mobile, with keyboard and both themes.
Verify a large real collection with
All/Snoozed/Completed/Archived, navigate both ways, check links and reload to
refresh current data. Verify API response bounds, no unrelated user rows and no
new semantic-provider dependency. This manual pass does not require activating
or repairing semantic relevance.
