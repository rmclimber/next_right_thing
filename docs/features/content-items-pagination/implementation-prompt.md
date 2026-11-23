# Implementation handoff: Content Items pagination

Implement this bounded vertical slice in the prepared worktree. You are an
implementation session; the planning session has prepared this prompt/spec/test
plan but has not implemented the feature. Inspect existing code before edits.

## Objective and current situation

NRT helps users choose worthwhile professional activities during available time.
Podcast ingestion can bring in over 1,000 episodes. Content Items currently
returns every owned item in one API response and filters/renders them in the
browser. Deliver **server-side cursor pagination, 50 items per page by default**,
with collection-wide disposition filters and simple Next/Previous controls.

Semantic relevance is deployed but not working due to AWS throttling per the
user on 2026-11-20. The user explicitly excludes troubleshooting that here.
Item listing uses the ordinary owned Aurora query, not semantic ranking or
embeddings. Implement and test independently of semantic-provider availability.

## Workspace, starting point and authorization

- Worktree: `C:/data/rick/projects/next_right_thing/dist/worktrees/content-items-pagination`.
- Branch: `codex/content-items-pagination`.
- Pinned base: `aef6c55409cb1a7683264711ee1180f6403ef3ca`, the last locally known
  `origin/main` at preparation time. It contains the integrated semantic code;
  its runtime success is not a prerequisite for this feature.
- The primary checkout has another session's embedding-concurrency fix branch
  (`codex/embedding-refresh-concurrency-fix`, observed at `ee4d08e`) and dirty
  planning documents. Do not switch, edit, stage, move or clean that checkout.
- Run `git status --short --branch` and `git worktree list` before work. The
  feature's three Markdown files and an updated `AGENTS.md` are intentionally
  seeded working-tree files; no commit was created. Treat them as handoff inputs.
- Authorize only pagination implementation/tests/feature docs in this worktree.
  Do not commit, merge, push, deploy, run a production migration, or create a PR
  until the user separately authorizes that action. No AWS CLI (`aws`) execution
  from Codex: if AWS operations become necessary, provide exact PowerShell
  commands for the user and say what output is needed.
- Keep coordination status/backlog ownership with the planning session. Return
  status updates in your final report; do not edit the primary planning files.
  Do not spawn other agents unless the user or applicable instructions request it.
- Planner-owned `docs/planning/PROJECT_STATUS.md` and `DECISIONS.md` are still
  uncommitted in the primary checkout and intentionally not duplicated here.
  This prompt/spec/test plan contain the necessary implementation context; read
  the primary planning records only if additional coordination context is needed.

## Read before changing code

Read in repository precedence order (paths below are relative to this worktree):

1. `AGENTS.md`, `docs/vision.md`, `docs/domain-model.md`, `docs/architecture.md`.
2. `docs/features/content-items-pagination/spec.md` and `test-plan.md`.
3. `ENGINEERING.md`, `docs/api-contracts.md` (`GET /content-items`),
   `docs/features/podcast-support/test-plan.md` and `apps/web/README.md`.
4. Implementation/tests listed below. The prepared spec is the intended feature
   behavior; existing runtime contracts remain unless explicitly changed there.

The repository has no new domain entity or architectural service to invent.
Inspect the migrations/indexes and existing tests, produce a short implementation
plan, then execute. Resolve routine details using the spec. If a real ambiguity
changes product semantics or requires significant architecture, explain it and
ask before implementing that change. Do not infer missing decisions from old
unchecked recommendation task lists. Preserve soft duration eligibility.

## Contract and acceptance summary

The complete contract is in `spec.md`; implement all of it and the test plan.

- `GET /content-items`: optional `limit` (default 50, 1–100), `filter` (default
  `all`; `all|snoozed|completed|archived`) and validated opaque `cursor`.
- Keep `content_items` and all item fields; add `next_cursor`, explicitly null
  on final/empty pages. Invalid query/cursor input returns 400; auth/500 behavior
  and tenant ownership remain. The default response is bounded, not unpaginated.
- Use existing descending `(discovered_at, created_at, id)` ordering with strict
  keyset comparison, filter-before-limit SQL and `LIMIT limit + 1`. No OFFSET,
  unbounded read, full count, provider call or Python-side collection slicing.
- Cursor: small versioned base64url JSON position/filter, strict shape/length/
  timestamp/UUID validation; no signing infrastructure or user credentials.
  SQL always scopes independently to the authenticated user. Replay/tampering
  must not grant data access; a deleted boundary row need not invalidate position.
- All includes every disposition. Snoozed is active with future snooze only.
  Keep missing-state defaults, owned source/state joins and expired-snooze behavior.
- UI requests server-filtered pages; Next/Previous, reset on filter, correct
  disabling/loading/retry, stale-response protection and honest page counts.
  No page-size picker, total count, snapshot guarantee or arbitrary page jumping.
- Fixed-dataset traversal is exhaustive without duplicates, including ties.
  Document current-data behavior as ingestion, deletion or dispositions change.
- Preserve article/podcast labels, durations, external links, source/state display,
  ownership, generic content contracts and independent recommendation eligibility.

## Ownership and expected files

Evolve these existing abstractions rather than adding a pagination framework:

- `backend/nrt_backend/content_items/repository.py` — bounded listing SQL/result.
- `backend/nrt_backend/lambdas/content_items/handler.py` — query validation/envelope.
- `backend/tests/test_content_items_repository.py`, `test_content_items_handler.py`.
- A focused new PostgreSQL pagination integration test, following
  `backend/tests/test_podcast_pipeline.py` isolated-schema patterns. Adapt existing
  podcast/API integration expectations only where the new contract requires it.
- `apps/web/lib/content-items-api.ts`, `apps/web/app/content-items/page.tsx`,
  `apps/web/app/content-items/page.test.tsx`; add focused client tests if useful.
- `docs/api-contracts.md`, this feature's spec/test plan and a concise feature
  implementation report. Minimal page CSS only if required by existing controls.

Do not modify recommendation scoring/service/repository, embedding modules or
refresh, shared DB helpers, ingestion, infrastructure/deployment workflows,
dependencies/lockfile, domain entities or global design docs to work around
throttling. No migration expected; an actual need must be justified first.
Architectural changes require an ADR and approval. New dependencies need explicit
justification; none is expected for this implementation.

## Validation

Use PowerShell from the pagination worktree root. Dependencies are not installed
for this new worktree by the planning session. Use existing tools/runtime if
available; install declared dependencies only if needed, with no lockfile changes.
Do not accidentally import source from an editable install of the primary checkout.

For backend checks, an existing Python 3.12 environment at the primary path was
previously usable; inspect it rather than assuming it remains available. Point
PYTHONPATH at **this** worktree and use that interpreter, or a worktree-local
environment with the declared backend test extra:

```powershell
$env:PYTHONPATH = "$PWD/backend"
& 'C:/data/rick/projects/next_right_thing/.venv/Scripts/python.exe' -m unittest discover -s backend/tests
pnpm --filter @nrt/web test:run
pnpm --filter @nrt/web exec tsc --noEmit --incremental false
pnpm build
git diff --check
```

For an isolated local environment the repository declares Python >=3.12 and
`python -m pip install -e './backend[test]'`; frontend setup is
`pnpm install --frozen-lockfile`. Do not copy private environment files or disable
TLS. Configure public build values using `apps/web/.env.local.example` as needed;
use documented test placeholders for a local static-build check, not invented
live infrastructure identifiers, and report that limitation.

Run real PostgreSQL tests against a **confirmed disposable**
`NRT_TEST_DATABASE_URL` (`postgresql+psycopg://...`). Follow isolated-schema cleanup;
never use an application database. Without such a URL, run deterministic tests,
report DB tests as skipped and leave database acceptance explicitly incomplete.
No AWS or paid model call is required. Do not treat mocks as proof of SQL paging.

## Integration, rollout and reporting

API before frontend; refreshed legacy tabs see the new pagination controls.
Old clients retain their item envelope but now get only the first page. New
clients must handle a missing/invalid `next_cursor` contract explicitly rather
than silently treating an old unbounded backend as successfully paginated.

The shared deploy workflow deploys ingestion before API/frontend, so a separate
embedding-infrastructure failure can block release even though this code is
independent. Leave it to the owning session; no workflow bypass/config change
belongs here. Do not fetch/rebase/cherry-pick the active embedding fix or deploy
merely to make this feature's release pass. Flag integration needs for the user.

At handoff report: problem/result; files changed; acceptance coverage and exact
test commands/results/skips; setup/build limitations; schema/API compatibility;
working-tree status and base commit; any remaining decisions/risks; and manual
acceptance instructions. Explicitly distinguish implemented, tested, committed,
merged and deployed. Leave changes reviewable without committing or publishing.
