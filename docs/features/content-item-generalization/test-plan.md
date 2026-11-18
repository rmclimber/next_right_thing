# Test Plan: Generic Content Item Contract

## Migration and Persistence

Given legacy Content Items and a `read_content_item` Recommendation Event,
when migration `20261116_0008` runs, then every existing item has non-null
`content_type = article`, duration is null, and the historical event is unchanged.
Given new items, when persisted, then all five allowed types and positive known
durations survive; null/unknown types and nonpositive durations are rejected.
When downgrading, only the two new columns/constraints disappear; items and
recommendation history remain.

## Writer and RSS

Given an older normalized message, when Writer handles it, then it stores an
article with unknown duration. Given an explicit valid type and duration, then
both persist. Given invalid values, then the message is acknowledged without
insertion. Given a duplicate, then no row or metadata is changed. Given ordinary
RSS/Atom entries, then Fetch retains the existing payload without type/duration
fields and without altering health behavior; Writer supplies article/null.
Fetch payloads remain compatible with both old and updated Writer versions.

## Candidates and Ranking

Given known duration, when deriving a candidate, then it overrides the summary
heuristic, including durations below five or above 240 minutes. Given null
duration, then existing summary estimation remains unchanged and is not written
back. Every candidate preserves item type and uses `consume_content_item`.
Given identical candidate data except type, then scores are equal. Existing
ranking, diversity suppression, and disposition eligibility tests continue to pass.

## APIs and Frontend

Given owned items, when listing, then type/duration, source provenance, default
and explicit dispositions, and deterministic order are preserved. Other users
receive no items. Given a recommendation, then its item exposes type and its
action is generalized. The selected decision persists as a new event.
Given an article with null duration, then the Content Items page renders its
existing presentation without an extra Article badge. Given either new or
legacy action name, then the recommendation renders. Open does not complete;
Complete/Snooze/Archive retain their existing request and advance behavior.

## Execution

From `backend`, run `.venv/Scripts/python.exe -m unittest discover -s tests`.
The PostgreSQL integration case in `test_content_item_contract_migration.py`
additionally runs when `NRT_TEST_DATABASE_URL` points to an isolated test database
using a `postgresql+psycopg://` URL. It creates and drops a unique test schema and
applies the actual migration chain, Writer/repositories, and API handlers.
The ordinary suite also checks generated PostgreSQL upgrade/downgrade DDL.

From the repository root, run `pnpm --filter @nrt/web test:run`,
`pnpm --filter @nrt/web exec tsc --noEmit --incremental false`, and `pnpm build`.
