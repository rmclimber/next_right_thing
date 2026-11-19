# Semantic relevance test plan

- Given synonyms with little lexical overlap and complete cached vectors, when
  semantic mode ranks the pool, then similarity can change the winner and the
  selected Goal appears in the explanation.
- Given multiple active Goals, when similarity is computed, then the maximum
  nonnegative cosine determines relevance; inactive Goals are not loaded.
- Given completed, archived, or future-snoozed items, when either ranking mode
  loads candidates, then those items remain absent. An expired snooze is eligible.
- Given an item longer than available time, when semantic relevance outweighs its
  duration penalty, then it can still win with its full known duration preserved.
- Given unknown duration, when candidates are created, then the existing runtime
  reading estimate applies and persisted duration stays null.
- Given recent decisions, when ranking runs, then the existing suppression pool
  is used before semantic ranking, including full-pool fallback when all are recent.
- Given baseline mode, when recommending, then no embedding cache is queried.
- Given shadow mode, when recommending, then baseline response, score, reason,
  and single persisted event are unchanged, and alternative IDs are logged.
- Given any missing/stale/invalid vector or cache failure, when semantic mode
  runs, then the entire baseline ordering is used without dropping candidates.
- Given changed Goal or Content Item text, when recommending before refresh,
  then the text hash invalidates the old vector. Model changes also invalidate it.
- Given repeated refresh or recommendation requests, when vectors are current,
  then refresh skips provider calls and recommendations never invoke a provider.
- Given provider errors or malformed output, when refreshing a page, then failures
  are counted, other subjects continue, and existing cache entries are retained.
- Given another user's subject IDs, when loading or saving vectors, then ownership
  joins prevent reading or overwriting their cache entries.
- Given the migration, when upgrading and downgrading, then only auxiliary tables
  change; Content Items and Recommendation Events remain intact. Deleting an
  unreferenced subject cascades its cache entries.
- Given frozen labeled evaluation cases, when evaluated repeatedly, then ordering
  and quality metrics are identical, including baseline fallback cases.

Run deterministic tests with `python -m unittest discover -s backend/tests`.
Set `NRT_TEST_DATABASE_URL` to a disposable PostgreSQL database URL using the
`postgresql+psycopg://` scheme for real migration/repository/eligibility tests.
Tests create and remove isolated schemas. See [operations and evaluation](operations.md).

## Automatic refresh

- Given multiple users and more than one page of subjects, when the scheduled
  worker runs, then each owned Content Item and active Goal is visited without
  duplicates, and inactive Goals are excluded.
- Given a repeated sweep, when cached vectors are current, then no provider call
  occurs. Changed text, model key, or invalid vectors cause regeneration.
- Given long Unicode HTML whose useful text occurs after the first transport
  chunk, when Data API reads it, then normalization/hash match the psycopg path.
- Given transient provider errors or an Aurora resume response, when retrying,
  then at most three attempts occur with bounded backoff. Permanent access errors
  are not retried within that operation.
- Given a partial provider/write/read failure, when the sweep continues, then
  successful subjects persist, failure is reported through the invocation and
  summary, and retry skips successes.
- Given generation or deadline exhaustion, when the worker stops, then it reports
  remaining work and fails for retry before starting more external operations.
  If later hydration exhausts the budget within a page, earlier subject writes
  have already persisted.
- Given another user's ID, when saving a vector, then ownership checks reject it.
- Given the infrastructure definitions, when validated, then the worker has no
  VPC attachment or paid network resource, concurrency is one, IAM scopes cluster,
  secret and model ARNs, and the disableable schedule runs every two hours.
- Given deployment packaging, when validating the workflow, then the SHA-keyed
  worker artifact and schedule controls are passed only under the database gate,
  and migrations run before the worker can be scheduled.

## Review regressions (2026-11-19)

- Given an exclusive lock on an embedding cache table, when semantic mode runs,
  then the cache statement timeout triggers and a baseline event is persisted.
- Given a Data API operation that can run for 45 seconds, when constructing its
  SDK client, then the read timeout is 60 seconds, inside the worker's 90-second
  reserve; Bedrock keeps its separate shorter timeout.
- Given empty normalized text, when refreshing, then failure is recorded without
  spending inference budget; matching cache hashes cannot make empty text
  semantically ready.
- Given tiny/large finite nonzero vectors, when normalizing, then direction and
  unit norm are preserved without underflow/overflow.
- Given duplicate item/Goal IDs, a nonboolean synthetic flag, naive timestamps,
  or invalid available/known duration, when evaluating, then reject the fixture
  before reporting misleading metrics.
