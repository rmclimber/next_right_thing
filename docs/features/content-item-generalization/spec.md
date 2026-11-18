# Generic Content Item Contract

## Objective

Stabilize the shared content contract for future podcast ingestion and semantic
relevance without implementing either feature. Extend existing abstractions;
see ADR-0007 and the durable domain, architecture, API, and ingestion contracts.

## Behavior

- Content Item remains durable generic content. `content_type` is required and
  constrained to `article`, `podcast_episode`, `video`, `research_article`, `book`.
  Migration classifies every existing item as an article.
- `duration_minutes` stores known/source-provided positive consumption minutes
  or null, separate from runtime estimates. Writer rejects values outside the
  PostgreSQL integer range and rejects booleans, fractions, and strings.
- Ordinary RSS/Atom entries retain the existing payload and omit type/duration.
  Writer defaults omitted fields to article/null, keeping both Writer versions
  compatible with Fetch. Explicit null type is invalid. Duplicate discovery
  never overwrites existing metadata.
- Candidate Actions are ephemeral `consume_content_item` actions, carry type,
  and prefer known duration over the unchanged deterministic summary estimate.
- Recommendation Events remain durable. Legacy `read_content_item` values are
  valid and unchanged; new decisions use `consume_content_item`.
- Content Items API adds type/duration; Recommendation API adds item type.
  Article UI and Open/Complete/Snooze/Archive controls keep their behavior.
- Source acquisition type remains independent of item kind. Future RSS podcast
  episodes keep `source_type = rss` and use `content_type = podcast_episode`.

## Boundaries and Lane Readiness

No podcast detection, enclosure parsing, players, discovery APIs, speculative
metadata, semantic ranking, embeddings, vector storage, ranking-weight changes,
new infrastructure, or dependency changes. Existing scoring, diversity,
eligibility, provenance, ordering, ownership, dispositions, and health remain.

Lane A owns podcast classification/ingestion, justified metadata, and podcast
presentation. Lane B owns semantic relevance/scoring infrastructure and future
embedding use. Both can use the shared type, duration, and consumption-action
contract immediately. There are no unresolved shared-contract decisions.

Deployment sequencing is defined in `docs/content-item-ingestion.md`; deploy a
separate frontend compatibility release before the recommendation backend and
apply the migration before updated backend readers/writers. RSS Fetch retains
its existing payload, so Fetch and Writer can deploy in either order.
