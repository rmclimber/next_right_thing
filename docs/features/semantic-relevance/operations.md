# Refresh and evaluate semantic relevance

## Local setup and refresh

Use Python 3.12+ and install the existing backend with `python -m pip install -e ./backend`.
For the full test suite use `python -m pip install -e "./backend[test]"` instead.
Its sole additional test dependency, PyYAML, parses infrastructure/workflow YAML
for resource-boundary regression tests and is not installed in Lambda packages.
The batch command additionally needs the AWS SDK (`boto3`), already supplied by
Lambda in production but installed separately for local tooling. No new backend
dependency is declared. Keep TLS verification enabled.

Apply migration `20261118_0009` through the existing approved migration workflow
before filling caches. Baseline works without the migration; opt-in modes fall
back if cache tables are absent. No migration or deployment is performed by the
refresh tool.

The operator environment needs database network routing, the existing
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SECRET_ARN` configuration, Secrets Manager
read permission, and AWS credentials/region with `bedrock:InvokeModel` on the
regional `amazon.titan-embed-text-v2:0` foundation model. Confirm model availability
and permission before running. Neither existing production Lambdas nor local
developer credentials are assumed to have this access. No IAM/network resources
are provisioned by this slice.

From the repository root, run in an appropriately connected environment:

```powershell
python -m nrt_backend.recommendations.backfill --user-id USER_SUB --kind goal --limit 100
python -m nrt_backend.recommendations.backfill --user-id USER_SUB --kind content_item --limit 100
```

Each result reports scanned/generated/skipped/failed and `next_after_id`. A
nonzero exit code indicates subject failures. Retry that same page until failures
are resolved; then pass its cursor with `--after-id UUID` for the next page.
Continue until the cursor is null (an exactly full final page can require one
empty follow-up). Repeat from the beginning for refresh: current text/model
vectors are skipped. Active Goals are scanned; Content Items are scanned regardless
of disposition so newly eligible items can already have vectors. Concurrent
content/text changes can require another pass. Rerun after ingestion or Goal edits.

The tool stores normalized vectors, exact-input SHA-256, model/representation
key, and generation time. Original text and provider error bodies are not logged.
Failures do not replace existing vectors; stale vectors remain unusable until
successfully refreshed. Different model keys can coexist; old-key cleanup is an
operator follow-up, not automatic deletion. Entity deletion cascades its vectors.

## Repeatable offline evaluation

Run the committed synthetic fixture without credentials or provider calls:

```powershell
python -m nrt_backend.recommendations.evaluate docs/features/semantic-relevance/evaluation-fixture.json
```

This fixture uses hand-assigned vector directions, padded to 256 dimensions only
when `synthetic` is true. It verifies mechanisms, not embedding quality. The four
cases yield three changed winners, 75% complete semantic coverage (one deliberate
missing-vector case), mean top-1 label 0.5 baseline vs 2.0 semantic, and mean
NDCG@3 0.7302 vs 1.0000. These numbers are intentionally constructed and must not
be used as evidence to enable semantic mode.

For a meaningful model evaluation, freeze at least 20 representative requests
across target professions and include vocabulary mismatches, irrelevant items,
older material, sparse summaries, varied durations, and competing Goals. Freeze
the same current time and selection pool for both modes. Obtain pools via the
existing RecommendationRepository reads, preserving its eligibility and latest-50
bound; apply recent-ID suppression exactly as production does before exporting:

```python
from datetime import datetime, timezone
import json
from pathlib import Path
from nrt_backend.recommendations.repository import RecommendationRepository
from nrt_backend.recommendations.embedding_repository import EmbeddingRepository
from nrt_backend.recommendations.embeddings import MODEL_KEY, semantic_relevances

user_id = "USER_SUB"
repository = RecommendationRepository()
now = datetime.now(timezone.utc)
goals = repository.list_active_goals(user_id)
items = repository.list_recent_content_items(user_id)
recent = set(repository.list_recent_recommended_content_item_ids(user_id))
items = [item for item in items if item["id"] not in recent] or items
cache = EmbeddingRepository().load(user_id, [item["id"] for item in items], [goal["id"] for goal in goals])
semantic_relevances(items, goals, cache)  # Reject missing, stale, or invalid vectors.
for kind, subjects in (("content_item", items), ("goal", goals)):
    for subject in subjects:
        subject["embedding"] = cache[(kind, subject["id"])]["vector"]
document = {"synthetic": False, "model_key": MODEL_KEY, "cases": [{
    "name": "case-01", "now": now.isoformat(), "available_minutes": 20,
    "goals": goals, "content_items": items,
    "labels": {item["id"]: None for item in items},
}]}
Path("dist/semantic-real-evaluation.json").write_text(
    json.dumps(document, default=lambda value: value.isoformat(), indent=2), encoding="utf-8")
```

Combine cases made with the same model key. Keep user text and vectors private
under ignored `dist/`; do not commit them. Have a reviewer label each candidate
without seeing either ranking: 0 irrelevant, 1 professionally useful, 2 directly
supports an active Goal. Replace every null label. Then run the same evaluator
against the frozen JSON. Real fixtures require full 256-dimensional vectors and
the current model key. The evaluator never writes Recommendation Events.
Also include separate incomplete-coverage cases to verify safe fallback.

Report mean top-1 relevance and NDCG@3 both overall and by profession, changed
winners, regressions, and semantic coverage. Review changed winners qualitatively;
use the same labels when comparing model/dimension/weight experiments. Record
provider/model key and fixture version with every result. The evaluator measures
ranking on already eligible pools; database eligibility is covered separately by
integration tests.

After approved deployment and refresh, start in shadow mode. Logs contain mode,
readiness, and each ranking's first three IDs, alongside existing selection/event
logs. Use CloudWatch request counts and Lambda Duration to compare coverage,
errors, and p50/p95 latency against baseline under comparable load. This slice
does not add persistent experiment history or random assignment; use a fixed
offline dataset and explicit evaluation windows. Baseline remains the rollback.
Do not activate semantic mode solely on synthetic fixture metrics. Recommend
activation only when blinded human judgments improve top-1/NDCG without material
profession-specific regression and latency/fallback rates are acceptable.

Evaluation input validation requires a JSON boolean `synthetic` flag, unique
nonempty IDs within each selection pool and Goal list, time-zone-aware item
timestamps, available time in 1..240 minutes, and positive known durations.
Duplicate IDs are rejected before metrics are computed; otherwise repeated
relevant items could inflate NDCG above one. Missing/invalid vectors still
exercise whole-pool baseline fallback. These checks do not replace blinded
human labels or validate real model relevance.

Optional request-time cache reads use a three-second PostgreSQL connection
timeout and a one-second server-side statement timeout per cache query, so a
cache-table lock triggers fallback. Existing baseline repositories, event writes,
operator refresh, and Secrets Manager timeout settings retain their defaults.
These settings bound cache DB operations, not the entire recommendation request.

## Automatic AWS refresh

ADR-0009 is approved and implemented in the ingestion stack. After an explicitly
approved deployment, a dedicated non-VPC Lambda is invoked by EventBridge
Scheduler using `rate(2 hours)` and an empty `{}` payload. No public API endpoint,
ingestion hook, or extra SQS consumer is added. The existing cache migration must
run first; the deployment workflow already runs migrations before ingestion.

GitHub Environment controls passed through `deploy-stack.yml`:

| Variable | Default | Effect |
| --- | --- | --- |
| `ENABLE_EMBEDDING_REFRESH` | `true` | Ingestion `EnableEmbeddingRefresh`; enables/disables the schedule only. |
| `EMBEDDING_REFRESH_MAX_EMBEDDINGS` | `100` | Ingestion `EmbeddingRefreshMaxEmbeddings`; 1..1000 subjects requiring inference per invocation. |
| `RECOMMENDATION_RANKING_MODE` | `baseline` | Independent ranking control; refresh can generate caches while serving baseline. |

The deployment's existing `ENABLE_DATABASE_BACKEND` gate controls the entire
ingestion deployment. The worker artifact uses
`lambda/embedding-refresh/<Git SHA>.zip` in the existing artifact bucket. Its
cluster, secret, database name, and regional Titan model permissions are defined
declaratively. The worker has no VPC attachment, DB password retrieval, NAT,
new endpoint, new secret, work queue, or additional migration.

The worker scans users and subjects deterministically in pages of ten, including
all Content Items and only active Goals. Subjects are hydrated and refreshed one
at a time within each page, so a later long-text read cannot discard earlier
successful writes. It transfers long serialized source
text in 4,000-character chunks and verifies the source fingerprint between
chunks. This preserves text-v1 even when an initial HTML prefix is only markup.
Invalid cache vectors are regenerated. Deleted/reowned subjects cannot be written.

Transient provider/Data API failures receive up to three attempts with one- and
two-second backoff. Aurora resume responses instead wait five and ten seconds
to allow a paused writer to wake. SDK automatic retries are
disabled for this path to avoid nested retry loops. A generation budget counts
subjects requiring inference, so retries can increase actual paid model calls.
Empty normalized text fails before the inference budget or provider is used.
The Data API client uses a 60-second read timeout, exceeding its 45-second SQL
timeout as AWS recommends; the Bedrock client retains its 10-second read timeout.
The Lambda has 512 MB, a five-minute timeout, concurrency one, and stops new
external work with less than 90 seconds remaining. No DB transaction spans
provider inference. Individual failures do not prevent later subjects from
being attempted; successful cache writes are retained.

Every sweep logs `embedding_refresh_summary` with users, scanned, generated,
skipped, failed, attempted, `remaining_work`, and `stop_reason`. Subject failures,
time/generation budget exhaustion, or incomplete scans fail the invocation.
Lambda retries asynchronous failures up to twice within one hour; Scheduler
separately retries failed delivery up to twice within one hour. The next
scheduled sweep also retries missing/stale work, skipping current successes.
Repeated delivery is safe for cache writes; inference can repeat if a prior
model call succeeded but its write failed. Original text, provider error bodies,
and credentials are not logged.

The explicit CloudWatch log group retains 14 days. A standard Lambda Errors
alarm tracks failed/incomplete runs; it has no notification target. Review this
alarm and summary logs after rollout. Lambda Errors cannot observe a Scheduler
delivery that never reaches the function; check Scheduler `TargetErrorCount`
and `InvocationDroppedCount` for the default schedule group during rollout.
Persistent `embedding_budget` means more
inference remains; persistent `time_budget` may indicate the corpus scan itself
is too large. Sweeps do not persist traversal cursors, so a large scan may need
the operator backfill tool or a separately reviewed queued/checkpointed design.
No DLQ is required for reconciliation: source rows remain the durable work to
be retried. This initial implementation targets a small corpus.

Turning the schedule off leaves manual invocation available and preserves
recommendations. Set ranking mode to baseline for ranking rollback. Provider
failure or missing cache coverage already falls back to baseline without either
configuration change. Two-hour latency is expected only for a healthy sweep
that fits its budget; failures/backlogs can take longer.

For local verification, run the complete backend suite with a disposable
`NRT_TEST_DATABASE_URL`. The Data API integration test executes the adapter's
parameterized SQL against PostgreSQL through a simulated SDK transport, enforcing
row/response size budgets. It verifies real cache compatibility, long Unicode
markup, ownership, active Goals, repeat runs, and text/model invalidation. Unit
tests exercise AWS responses, errors, deadline limits, and retries without
credentials or model calls. Infrastructure tests protect schedule, IAM, network,
budget, and migration-before-worker deployment boundaries. Additionally run
`cfn-lint infra/ingestion/ingestion.yaml infra/api/api.yaml` with the development
CloudFormation linter.

No live deployment, Bedrock invocation, or AWS CLI operation was performed for
local validation. Region/model access, deployed Data API behavior, actual costs,
real relevance quality, and AWS latency still require approved rollout checks.

The 2026-11-19 [implementation review](review-2026-11-19.md) records fixes and
remaining deployment checks.
