# Semantic recommendation relevance: initial slice

## Inspection and proposal

The synchronous Python Recommendation Service reads the latest 50 eligible,
owned Content Items and active Goals through psycopg. Completed, archived, and
future-snoozed items are excluded in SQL. Recent-decision diversity suppression
then chooses the selection pool, falling back to the eligible pool when needed.
Duration is a score, never a hard filter. Baseline weights are recency 0.40,
lexical relevance 0.35, duration fit 0.25. There is no persisted interests field.
Content Items have title, nullable summary, generic type, and nullable duration.

1. **Text:** embed title plus summary for Content Items, title plus description
   separately for each active Goal. Strip markup, decode entities, collapse
   whitespace, and cap each representation at 4,000 characters. Exclude type,
   source branding, URLs, dates, duration, lifecycle state, and user identity.
   Version this representation; interests are represented only when expressed
   in existing Goals. Do not invent a profile or Topic relationship.
2. **Provider:** initially Amazon Bedrock `amazon.titan-embed-text-v2:0`, normalized
   float vectors at 256 dimensions. This fits the existing AWS identity/runtime
   approach and requires no external API secret or model hosting. Compare a
   higher dimension/model only after relevance evaluation. OpenAI/Cohere are
   viable alternatives but add provider/access decisions without demonstrated
   benefit here. An injected provider supports deterministic local testing.
3. **Lifecycle:** two auxiliary tables, one per existing entity, with foreign
   keys, model/representation key, SHA-256 of the exact input, vector, and creation
   time. An explicit resumable batch command scans one user's Content Items and
   active Goals, skips current valid vectors, and replaces stale ones. Failures
   leave existing cache data intact, report counts, and permit retry. Changes to
   text/model/representation invalidate cached vectors. Recommendation requests
   only read vectors; they never invoke an embedding provider. ADR-0009 adds an
   approved two-hour, non-VPC Data API refresh Lambda; ingestion hooks stay out
   of scope. The operator CLI continues to use psycopg.
4. **Storage/search:** use PostgreSQL JSONB arrays and exact in-process cosine
   over the unchanged 50-item pool. No vector index, extension, new dependency,
   or AWS resource is needed. Aurora supports pgvector on documented versions,
   but `infra/database/database.yaml` does not pin EngineVersion, so deployed
   support is unverified. Before considering indexed retrieval, inspect
   `SELECT version();` and
   `SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'vector';`.
   Indexed retrieval would change candidate recall and needs a separate decision.
5. **Ranking/fallback:** preserve all eligibility, suppression, recency, duration,
   and tie rules. Use maximum clamped cosine (0..1) across active Goals in place
   of the lexical 35% component. Require complete current valid embeddings for
   the entire selection pool and all active Goals; otherwise retain the entire
   baseline ranking, avoiding comparisons on mixed lexical/semantic scales.
   No Goals also uses baseline. `baseline` (default) reads no embedding tables;
   `shadow` logs both rankings but serves/persists baseline; `semantic` serves
   semantic results when coverage is complete. Cache read failures fall back.
   Request-time cache DB connection/statement timeouts are shorter than the
   baseline defaults, preserving fallback when a cache table is locked.
   Historical events and public response shape do not change.
6. **Evaluation:** run fixed synthetic fixtures with injected vectors to verify
   ordering, fallback, and eligibility invariants. Separately freeze real candidate
   pools, Goals, time, recent IDs, and real model vectors; obtain blinded human
   labels (0 irrelevant, 1 useful, 2 directly useful) and compare top-1 relevance,
   NDCG@3, changed winners, coverage/fallback, and runtime. Synthetic tests verify
   plumbing; they do not establish model quality. Use shadow before activation.
   Reject duplicate IDs and ambiguous fixture flags/timestamps before computing
   metrics to keep comparisons valid and independent of host time zone.

## Plan and review boundary

Implement the text/provider contract, additive cache migration and batch tool,
opt-in ranking, tests, offline evaluation, and operational documentation. Keep
podcast ingestion/presentation, domain entities, and event schema unchanged.

The private API Lambdas have a Secrets Manager endpoint but no NAT or Bedrock
endpoint. Do not add network resources or call Bedrock from request handling.
The operator batch requires an environment with both database routing and
Bedrock access. The user approved the non-VPC Data API worker alternative in
ADR-0009. Its infrastructure definitions add a Lambda, two-hour EventBridge
Scheduler schedule, scoped roles, logs, bounded retries, and an Errors alarm.
No NAT, VPC endpoint, queue, or additional schema migration is introduced.
Deployment remains subject to explicit authorization.

Sources: [Titan V2 limits and dimensions](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html),
[Titan request format](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html),
[Aurora pgvector support](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html).
