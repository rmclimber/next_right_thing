# Semantic relevance

NRT can use precomputed semantic similarity to active Goals to rank the existing
eligible Content Items. Interests expressed in Goals participate; no separate
interests/profile persistence is introduced. See [design](design.md) and
[ADR-0008](../../adr/adr-0008-semantic-relevance-cache.md).

`RECOMMENDATION_RANKING_MODE` selects `baseline` (default), `shadow`, or
`semantic`. Invalid values safely select baseline. This is environment-wide
configuration, not a user-controlled API query parameter. The GitHub Environment
variable of the same name passes through the deployment workflow to the API
stack's `RecommendationRankingMode` parameter. Only the recommendation Lambda
receives it. Changing it requires an explicitly approved configuration deployment.

Baseline performs no cache reads. Shadow computes and logs the first three IDs
from both rankings and readiness but serves and records exactly the baseline
decision. Semantic replaces lexical relevance with maximum nonnegative cosine
similarity to an active Goal, retaining weights 0.40/0.35/0.25 and tie-breaking.
Explanations describe similarity to the best matching Goal and report actual
estimated/available minutes, including over-window items.

Candidate eligibility, the latest-50 bound, recent-decision suppression and its
fallback, known/unknown duration resolution, and soft duration scoring are
unchanged. Semantic relevance never admits or excludes a candidate. All current
selection-pool Content Items and all active Goals need valid current vectors.
Missing, stale, incompatible, zero, nonfinite, or wrong-size vectors, cache read
failures, or no active Goals use the entire baseline ranking. There is no mixing
of lexical and semantic relevance scores within a request.

No recommendation-time inference, API response shape change, new domain
relationship, or history migration is introduced. Only the selected decision is
persisted. Embeddings are private derived caches accessed through owned rows.
Model and representation changes require a new model key and backfill.

Provider failures affect only background/operator refresh work. Successful subjects persist;
failed subjects retain prior data and can be retried. Until valid coverage is
available, recommendations continue using baseline.

The approved automatic refresh worker runs outside the VPC every two hours,
using Data API for owned Content Item/active Goal reads and cache writes, and
Bedrock for embeddings. It shares the operator tool's representation and subject
refresh logic. The schedule can be disabled independently of ranking mode;
baseline mode can still generate caches for subsequent shadow evaluation.
Bounded sweeps retry transient failures, keep successful writes, and surface
incomplete work through summary logs and a Lambda Errors alarm. No ingestion or
Goal mutation hook is required; healthy refresh can lag changes by roughly two
hours plus runtime. See ADR-0009 and the operations procedure.

Independent interests, new retrieval pools, vector indexes,
personalized weights, calibrated similarity thresholds, and podcast ingestion or
presentation are outside this slice.
