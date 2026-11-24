# Planning decision log

## Pagination control placement follow-up — 2026-11-24

- User requested matching pagination widgets at the top and bottom of the display
  plus numbered Go To Page controls. Top/bottom placement uses the existing shared
  page/filter/size state; both navigation regions have distinct accessible labels.
- User selected visited pages plus the next available page using existing cursors.
  Both bars show numbered buttons with the current successful page highlighted.
  Direct numbered jumps use saved cursors; unchanged boundaries retain later
  positions, changed/final boundaries invalidate downstream history. Filter/size
  changes reset history; failed/stale responses do not advance it.
- No total count, unknown-page jump, backend change or snapshot is introduced.
- Local baseline `555ca6a` contains the earlier compact controls/page-size change.
  The user subsequently authorized committing and pushing the placement/numbered
  navigation changes and planning documents directly to main on 2026-11-24.
  Deployment outcome remains unverified; no manual deployment is requested.

Recorded 2026-11-19; updated 2026-11-24. Dates below distinguish recording from an original
decision date when known. This log indexes constraints; substantial architecture
decisions remain in [ADRs](../adr/). Entries do not authorize deployments.

## Soft duration eligibility

- Date: recorded 2026-11-19; original acceptance date unknown.
- Status: **Accepted**; explicitly reported accepted in the user's planning
  handoff and corroborated by domain/specification/code/tests.
- Decision: exceeding available time lowers duration-fit score but does not
  exclude a Content Item. Keep eligibility distinct from relevance and fit.
- Rationale: preserve sensible flexibility while using time as a ranking signal.
- Alternative: strict maximum-duration filtering; not the accepted behavior.
- Consequences: over-window items can win, including known-duration episodes;
  explanations must accurately state the actual duration. Changes need an
  explicit product decision and regression coverage.
- Evidence: [domain model](../domain-model.md),
  [podcast spec](../features/podcast-support/spec.md),
  [scoring](../../backend/nrt_backend/recommendations/scoring.py),
  [semantic test plan](../features/semantic-relevance/test-plan.md).

## Generic content and consumption contracts

- Date: recorded 2026-11-19; ADR-0007 has no explicit decision date.
- Status: **Accepted**, per ADR-0007 and committed implementation.
- Decision: evolve Content Item with independent item type and nullable known
  duration; retain ephemeral Candidate Actions and durable Recommendation Events.
  New actions use `consume_content_item`; historical `read_content_item` stays valid.
- Rationale/alternative: extend existing abstractions instead of separate
  per-medium entities or rewriting history.
- Consequences: RSS remains the source type for podcasts; preserve known versus
  estimated duration and schema/Writer/frontend rollout ordering.
- Details: [ADR-0007](../adr/adr-0007-generic-content-item-contract.md).

## Initial podcast boundaries

- Date: recorded 2026-11-19; committed as `f0280b5` on 2026-11-18.
- Status: **Accepted in committed specification**; live acceptance unverified.
- Decision: identify episodes by valid HTTP(S) audio enclosures; store enclosure
  in existing URL and description in summary; external listening only. Unknown
  duration keeps the common fallback. Duplicate discovery is insert-only.
- Rationale: deliver usable discovery through existing ingestion and UI contracts.
- Alternatives/deferred: player, playback state, transcription, directory search,
  new media/source fields, historical reclassification and a listening-time model.
- Consequences: historical articles stay unchanged; missing audio MIME metadata
  is not guessed. Existing fields also supply semantic input without transcription.
- Details: [podcast spec](../features/podcast-support/spec.md).

## Cached semantic reranking

- Date: recorded 2026-11-19; ADR-0008 original decision date unspecified.
- Status: **Accepted according to ADR-0008, now committed in `63ddedf`**. Prior approval
  is repository-reported, not newly granted or independently verified here.
- Decision: precompute versioned, text-hashed Titan V2/256-dimensional vectors;
  PostgreSQL JSONB caches, exact cosine in the existing bounded pool; baseline
  default, optional shadow/semantic; whole-pool fallback on incomplete coverage.
- Rationale/alternatives: bounded reranking needs no vector index or database;
  provider calls belong outside request handling. Keep eligibility/duration fixed.
- Consequences: additive migration and refresh required; real human evaluation
  precedes activation. Synthetic scores are not evidence of model quality.
- Details: [ADR-0008](../adr/adr-0008-semantic-relevance-cache.md),
  [design](../features/semantic-relevance/design.md),
  [evaluation procedure](../features/semantic-relevance/operations.md).

## Scheduled embedding refresh

- Date: 2026-11-18 approval **recorded in ADR-0009**; inspected 2026-11-19.
- Status: **Accepted according to ADR-0009, now committed in `63ddedf`**; implemented
  locally, not deployed per that record. No renewed architectural approval is
  inferred or required merely to preserve this status.
- Decision: dedicated non-VPC Lambda + Data API + Bedrock every two hours,
  bounded work/retries, shared caches. Application database paths stay unchanged.
- Rationale/alternatives: reuse existing Data API precedent; defer NAT/Bedrock
  endpoint, coordinator/private Lambda pair, and event-driven queue complexity.
- Consequences: separate infrastructure/release review; refresh can run while
  ranking remains baseline. Freshness depends on healthy sweeps and budgets;
  Aurora wake cost and regional model access need verification. Current schedule
  default is enabled and must be considered explicitly at rollout.
- Details/cost scenarios: [ADR-0009](../adr/adr-0009-automatic-embedding-refresh-proposal.md).
  Cost figures there are historical proposal estimates, not current verified pricing.

## Planning continuity and release authority

- Date: 2026-11-19.
- Status: **Accepted**, explicit user planning handoff.
- Decision: use [PROJECT_STATUS.md](PROJECT_STATUS.md), this log, the existing
  [feature backlog](../features/backlog.md), feature specs/test plans and ADRs.
  Plan and coordinate; implement features only when instructed. Do not commit,
  merge, push or deploy without approval or alter another session's work.
- Rationale/alternative: a small repository memory system avoids duplicating
  project history or creating a second backlog.
- Consequences: record evidence and uncertainty, preserve ownership boundaries,
  and distinguish code, integration, release, and manual acceptance every session.

## Pagination can proceed independently of semantic runtime

- Date: 2026-11-20.
- Status: **Accepted for implementation handoff**, user requested prompt/worktree
  preparation after confirming semantic relevance is deployed but throttled.
- Decision: implement bounded Item API/UI pagination in its own worktree using
  existing Aurora ownership/state queries. Default 50, server filters and cursor
  navigation; no embedding/model calls or semantic troubleshooting in this slice.
- Rationale/alternative: the listing handler/repository have no semantic-service
  dependency. Waiting for runtime embeddings would unnecessarily block this work.
- Consequences: base `aef6c55` includes semantic code, which need not be operational
  for implementation/tests. The shared deploy workflow's ingestion-before-API
  sequence can still block release. Keep the embedding-fix branch separate and
  coordinate approved integration/release rather than modifying infra here.
- Details: [pagination spec](../features/content-items-pagination/spec.md),
  [handoff](../features/content-items-pagination/implementation-prompt.md).


## Pagination integration, cleanup and compact controls

- Date: 2026-11-24.
- Status: **Accepted by explicit user instruction**. Original pagination is
  integrated as `2498a3e` and deployed per user; the UI follow-up is authorized
  directly on main but remains uncommitted and undeployed.
- Decision: replace large Next/Previous text buttons with compact chevron buttons,
  preserving accessible names, hover labels and loading/final-page disabling.
  Expose 10/25/50/100 items per page, default 50, through the existing API limit.
  Restart at page one and clear cursor history when size changes; retain the
  selected filter. Size is local page state and resets to 50 on reload.
- Rationale: meet the user's preference through the existing cursor/API/page
  abstractions. No backend, schema, dependency, recommendation or architecture
  change is required. This supersedes the original slice's no-size-picker boundary.
- Cleanup: restore planning files selectively, preserve current feature docs,
  archive all five obsolete worktree directories and a complete Git bundle,
  then unregister worktrees and remove 28 integrated/equivalent local branches.
  Keep the planning stash, backup branch and `content/multiple_types` with its
  two unmatched patches. Remote branches remain untouched.
- Consequences: main is the only active checkout; recovery material remains local
  in ignored `dist/git-cleanup-backup-2026-11-24/`. Neither deployment reports nor
  patch equivalence establish real DB/manual acceptance. No commit or push is
  authorized for the current documentation/UI update.
- Evidence: [project status](PROJECT_STATUS.md),
  [pagination specification](../features/content-items-pagination/spec.md) and
  [implementation report](../features/content-items-pagination/implementation-report.md).
