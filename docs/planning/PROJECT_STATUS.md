# Project status

Last updated: **2026-11-24, America/Los_Angeles**. This snapshot separates
repository evidence, user-reported deployment and outstanding validation.
Read [decisions](DECISIONS.md) and [backlog](../features/backlog.md) next;
document precedence remains in [AGENTS.md](../../AGENTS.md).

## Project snapshot

- Primary checkout: `C:/data/rick/projects/next_right_thing`, branch `main`,
  HEAD and stored `origin/main` at `2498a3ef42d6442ea59fff43afaa67b4e641f390`.
  This is the sole registered worktree after cleanup on 2026-11-24.
- Pagination is **committed and integrated** as `2498a3e` (original feature
  commit `e877d77`). The user reported the PR merged/pulled on 2026-11-23
  and deployment completed on 2026-11-24. No independent deployment-run or
  authenticated live-browser verification is claimed.
- Content Items listing uses bounded server-side keyset pagination, default 50,
  collection-wide All/Snoozed/Completed/Archived filters, current-data semantics,
  cursor navigation and honest page counts. No schema migration was needed.
- Follow-up authorized on 2026-11-24 directly on main: compact chevron buttons
  with accessible labels and a 10/25/50/100 page-size selector (default 50).
  Changing size restarts page one, retains the filter and clears cursor history.
  This follow-up is local/uncommitted and has not been deployed.
- Existing capabilities: Cognito sign-in; Goals and lifecycle; RSS Content Sources
  and fetch health; article/podcast ingestion; recommendations for 1–240 minutes;
  Complete, 24-hour Snooze, Archive, history, provenance, diversity and themes.
- Recommendation eligibility is independent of browsing pagination. Its latest-50
  eligible-item pool, active Goals and recency/relevance/duration weights
  0.40/0.35/0.25 remain unchanged. Known duration wins over the summary estimate.
  **Duration remains soft scoring, not a hard eligibility filter.**
- Architecture remains static Next.js/S3/CloudFront, Cognito/API Gateway/Python
  Lambdas, private Aurora/psycopg/Alembic, and scheduled RSS ingestion. Semantic
  cache refresh uses the existing non-VPC Data API/Bedrock path. See
  [architecture](../architecture.md).

## Deployment and validation

- Pagination: deployed per user on 2026-11-24; real PostgreSQL integration and
  the full manual acceptance pass remain outstanding. Deployment alone does not
  establish those checks passed. Exact deployed SHA/environment was not independently
  inspected; `2498a3e` is the locally observed integrated commit.
- Original pagination verification recorded 2026-11-20: backend 241 tests run,
  OK with seven PostgreSQL skips; web 39 tests across six files passed;
  TypeScript, static build with test placeholders and whitespace checks passed.
  See the [implementation report](../features/content-items-pagination/implementation-report.md).
  Follow-up checks on 2026-11-24: web 41 tests/six files, TypeScript, static build
  with public test placeholders and whitespace checks passed. Backend tests were
  not rerun for the frontend-only follow-up; no new DB/manual acceptance is claimed.
- Semantic relevance: deployed but nonoperational due to AWS throttling per user
  on 2026-11-20; current runtime recovery, ranking mode and cache health remain
  unverified. Do not infer recovery from pagination deployment.
- Embedding concurrency fix: patch integrated as `351d01b`, equivalent to original
  `ee4d08e`. Its inclusion in repository history does not independently establish
  its runtime outcome.
- Podcast `f0280b5`: deployment, Healthy source status and an episode recommendation
  were user-reported. External playback, all dispositions and repeat-ingestion
  acceptance remain incomplete. Retain the data-science episode/Mandarin Goal
  mismatch as a relevance evaluation case.
- Historical 2026-11-19 public checks found podcast UI assets and parsed 1,046
  episodes from the provided feed. They did not inspect authenticated database rows.
  Historical Source Dispatch `DatabaseResumingException` handling remains a
  separate reliability follow-up.
- The shared workflow deploys ingestion before API/frontend. No workflow bypass,
  AWS CLI call, production migration or deployment was performed in this session.

## Worktree and branch cleanup — 2026-11-24

User authorized restoration and cleanup after moving the primary checkout onto
main. Evidence: `git status`, `git worktree list`, branch refs, bundle verification
and per-branch `git cherry origin/main` checks.

- Restored AGENTS.md, README.md, docs/features/backlog.md and both docs/planning
  files from the preserved planning stash; verified their stashed blob hashes
  before this requested update. Current integrated pagination feature docs were
  preserved instead of restoring the older stashed handoff versions.
- Archived five complete directories, including ignored local files and the
  pagination worktree's uncommitted AGENTS.md, then unregistered them:
  content-items-pagination, frontend-action-compatibility, nrt-main-integration,
  nrt-podcast and nrt-semantic. No secondary active worktree remains.
- Deleted 28 obsolete local branch names after preserving their tips in a verified
  complete Git bundle and checking no unmatched non-merge patches. Squash-merged
  equivalents were handled explicitly. No remote branches were deleted.
- Remaining local branches: `main`, `backup/main-before-cleanup-2026-11-24` at
  `f65933c`, and `content/multiple_types` at `1930062`. The latter has two
  unmatched patches and is retained for review. Do not bulk-delete it.
- Recovery material is local and ignored under
  `dist/git-cleanup-backup-2026-11-24/`: repository.bundle, original refs,
  removed-branch manifest, archived directories and RECOVERY.md instructions.
  Keep it before any dist cleanup. The original planning stash remains saved.
- Planning/guidance and current UI changes remain unstaged/uncommitted on main.
  No commit, push, merge, PR or deploy is authorized by this update.

## Current work and next actions

1. Review the local compact-pagination/page-size follow-up and planning changes.
   Commit/push only after separate approval; refresh browser assets after an
   eventual approved frontend release.
2. Run real PostgreSQL paging/ownership tests using a confirmed disposable
   `NRT_TEST_DATABASE_URL`; never use an application database. Follow the
   [test plan](../features/content-items-pagination/test-plan.md).
3. Complete live pagination acceptance on a large collection: filters, Next/Previous,
   final/empty pages, article/listening links, retry and current-data behavior.
   Check the new size selector separately after its release.
4. Review `content/multiple_types` unmatched patches before further cleanup.
   Preserve recovery archives and stash until their contents have been reviewed.
5. Continue separately scoped semantic operational acceptance and relevance
   evaluation. Capture exact texts/mode for incorrect Goal attribution.
6. Future candidates remain in the single backlog: truthful time/Goal explanations,
   manual source/item Goal links, better article duration, cross-device handoff,
   and bookmarks. No feature implementation is authorized by this list.

Open uncertainty: real PostgreSQL/query-performance evidence, full browser
acceptance, semantic runtime/quality/cost evidence, historical podcast acceptance,
and whether the retained unmatched patches remain useful.
