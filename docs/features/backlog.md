# Feature Backlog

## Next

### P0 — Close podcast and semantic track acceptance

- Status: review/validation pending; see [project status](../planning/PROJECT_STATUS.md).
- Update (2026-11-20): semantic slice is deployed but not operational due to AWS
  throttling, per user. Do not troubleshoot it in the pagination session. Closing
  its operational acceptance is not a prerequisite for pagination implementation.
- Progress (2026-11-19): user confirms podcast feed now shows Healthy and reports
  an episode recommendation; full playback/disposition/idempotency acceptance
  remains incomplete. Semantic work is committed as `63ddedf` on
  `codex/semantic-relevance`; PR preparation is user-reported, review pending.
- Objective/value: complete discovery/relevance acceptance while independent,
  bounded work such as pagination can proceed in parallel.
- Scope: review the complete semantic diff, PostgreSQL integration, combined
  regression checks, podcast manual acceptance, real semantic evaluation and
  separately approved integration/deployment. No new ranking architecture.
- Dependencies: coordinate primary-worktree ownership; disposable PostgreSQL;
  approved release and model access for live checks.
- Observed runtime issue (2026-11-19): user-run Source Dispatch failed before
  queuing jobs with `DatabaseResumingException`. Retry after Aurora wakes for
  immediate diagnosis; propose bounded resume handling and a regression test
  before declaring cold-start dispatch reliable. No implementation authorized.
- Acceptance: exact reviewed commits and test results recorded; podcast release
  and manual status explicit; baseline fallback/soft duration preserved; real
  labeled evaluation informs a separate shadow/semantic activation decision.
- Parallelism: fixture/label preparation and podcast acceptance can run alongside
  semantic review, with one owner for implementation and shared planning files.

### Content Items pagination — merged and deployed; acceptance pending

- Integrated as `2498a3e` on main (original feature commit `e877d77`).
  PR merge/pull user-reported 2026-11-23; deployment user-reported 2026-11-24.
- Implemented: server-side cursor pagination, default 50, collection-wide
  disposition filters, Next/Previous, bounded queries and honest page counts.
  Recommendation candidate selection and soft duration eligibility are unchanged.
- 2026-11-24 follow-up authorized directly on main: compact accessible chevrons and
  10/25/50/100 items per page (default 50); size changes restart page one with the
  current filter. Follow-up changes remain uncommitted and undeployed.
- Verification: original backend 241 tests, seven PostgreSQL skips; web 39 tests,
  TypeScript and static build passed. Real DB and full manual acceptance remain
  outstanding; see [report](content-items-pagination/implementation-report.md)
  for follow-up results and [test plan](content-items-pagination/test-plan.md).
- The feature worktree was archived/unregistered and its local branch deleted
  during authorized 2026-11-24 cleanup. Main is the sole active checkout. Recovery
  details and the two unmatched patches retained on `content/multiple_types`
  are recorded in [project status](../planning/PROJECT_STATUS.md).
- [Specification](content-items-pagination/spec.md); the original
  [implementation prompt](content-items-pagination/implementation-prompt.md)
  is historical handoff context, not current worktree/setup instructions.

### P1 — Trustworthy recommendation explanations

- Status: proposed; not approved for implementation.
- Objective/value: let users trust claims about time fit and Goal relevance.
- Scope: correct baseline explanations that currently say an over-window item
  “fits”; show actual estimated/available time using existing response fields.
  Preserve eligibility, scores, tie-breaking and historical event text.
- Goal attribution investigation: user reports a data-science episode attributed
  to their Mandarin-learning Goal despite ML-interview/Bayesian-statistics Goals.
  Exact Goal/episode wording and deployed ranking mode have not been captured.
  Lexical matching counts generic words such as `learn`, a plausible false-match
  cause, not a confirmed diagnosis. Semantic mode chooses maximum similarity
  without a calibrated attribution threshold and remains opt-in/fallback-capable;
  PR merge alone does not establish this example is fixed.
- Dependencies: settle semantic integration or explicitly assign ownership of
  shared `recommendations/service.py`; agree final wording in a small spec.
- Acceptance: fitting, slightly over-window and substantially over-window items
  get truthful new explanations; over-window items can still win; known/unknown
  duration and legacy actions retain their behavior; deterministic tests cover
  the changed user-visible text and unchanged selection.
- Additional acceptance: reproduce the reported cross-Goal mismatch with frozen
  texts and evaluate baseline/shadow/semantic outcomes. Do not confidently name
  an unrelated Goal on weak evidence. Agree evidence/wording policy in the spec;
  any ranking correction is explicit, separately scoped and regression-tested.

## Soon

### P2 — Manual Goal associations for Content Sources and Content Items

- Status: proposed from user feedback on 2026-11-19; design required.
- Objective/value: express why a feed or episode is useful without depending
  entirely on lexical overlap or embeddings.
- Proposed starting point: let a user associate a Content Source with one or
  more of their Goals; consider per-Content Item assignments/overrides as a
  follow-up or part of the smallest coherent flow. Support articles as well as
  podcasts. Keep deterministic manual intent distinct from inferred similarity.
- Decisions before implementation: source inheritance versus item override/
  exclusion, multiple Goals, effects on ranking/explanations versus eligibility,
  and treatment of paused/completed/archived Goals. Do not implicitly turn an
  association into a hard eligibility filter or replace semantic evaluation.
- Dependencies: the domain currently defers persisted Content Item/Goal
  relationships; propose the domain/data/API changes and ADR for architectural
  consequences, obtain required approval, and coordinate recommendation-service
  ownership after semantic integration. Avoid introducing a Topic framework just
  to support explicit user associations.
- Acceptance: users can assign/remove only their own Goals; future attribution
  reflects the agreed source/item precedence; manual evidence is identified
  accurately; edits affect future decisions without rewriting history; inactive
  Goals, multiple assignments and cross-user access have deterministic coverage.

### P2 — Better article-duration estimates

- Status: proposed; already identified in [roadmap](../roadmap.md).
- Objective/value: make short-session recommendations reflect article length
  more accurately when feeds include full content.
- Scope: define reliable full-entry evidence and derived word count; retain a
  conservative excerpt-only fallback. Evolve existing ingestion and duration
  resolution; do not write estimates into known `duration_minutes`.
- Dependencies: agree evidence/fallback semantics in a feature spec; review any
  additive migration/API changes and podcast interaction before implementation.
- Acceptance: full-content, excerpt-only, missing/HTML content, and duplicate
  ingestion cases behave deterministically; known podcast duration wins;
  estimates remain distinct from source-provided duration; soft eligibility and
  article/podcast controls remain intact. Final numeric policy requires design.

### P3 — Cross-device handoff for episodes and articles

- Status: backlogged from user feedback on 2026-11-19; discovery/design first,
  not a commitment to native push or a new integration.
- Objective/value: move a recommended episode from desktop NRT to Apple Podcasts
  on an iPhone without manually searching; later open an article on an iPad.
- Scope candidates: copy/share links or QR handoff as a small first step;
  investigate exact-episode Apple Podcasts links and their required identifiers
  before selecting a mechanism. Sharing an audio enclosure URL alone does not
  establish that Apple Podcasts will open the matching catalog episode.
- Dependencies/questions: current podcast `url` is the audio enclosure; the
  original episode permalink/catalog identifiers are not separately persisted.
  Determine discoverable identifiers and device/browser behavior before proposing
  metadata/API changes. Confirm whether a phone opening NRT itself meets the need
  or whether direct Apple Podcasts handoff is essential. Defer account pairing,
  notifications/native apps and external sending until justified and authorized.
- Acceptance: the chosen handoff reaches the same episode on the destination
  device with a useful fallback when app linking fails; a portable article path
  is documented; no user token/private context is embedded in public handoff URLs;
  sharing/opening does not mark the item Complete. Verify on the user's actual
  desktop/iPhone/Apple Podcasts setup rather than assuming deep-link support.

### P3 — Bookmark Content Items

- Status: proposed; already identified in [roadmap](../roadmap.md).
- Objective/value: return to useful material encountered during a short session.
- Scope: smallest save/unsave and saved-items return path through existing Item
  APIs/UI. Define its relationship to dispositions before adding persistence.
- Dependencies: product decision on whether bookmarks affect eligibility;
  approved spec/data/API contract. Do not invent a new disposition implicitly.
- Acceptance: users save, find and unsave owned articles/episodes; other users
  cannot access them; repeated saves are safe; Complete/Snooze/Archive and
  recommendation behavior follow the agreed contract with regression coverage.
- Parallelism: design can accompany duration evaluation; simultaneous coding
  requires distinct ownership of shared Item repository/API/UI/migration files.

## Later / Ideas
- randomly select among older ideas
- support addition of research articles, books, book chapters
- support longer-term roadmaps
