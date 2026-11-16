# ADR-0007: Generic Content Item and Consumption Action Contract

## Status

Accepted

## Context

RSS ingestion and recommendations currently assume articles. Podcast ingestion
and semantic relevance need a stable shared contract before independent work.
The existing Content Item, Candidate Action, and Recommendation Event
abstractions already have the appropriate persistence boundaries.

## Decision

Extend Content Item with non-null text `content_type`, constrained to `article`,
`podcast_episode`, `video`, `research_article`, or `book`, and nullable integer
`duration_minutes`. Migration `20261116_0008` backfills existing rows as articles
using a retained database default. Known duration must be positive, matching the
existing Recommendation Event duration constraint; unknown duration stays null.
No speculative type-specific metadata or content-type framework is introduced.

Content Source `source_type` is the acquisition mechanism/provider, independent
of Content Item `content_type`. RSS continues to emit only `article` and null
duration. Writer accepts omitted type/duration as `article`/null for older
messages, validates explicit values, and retains insert-only idempotency.

Candidate Actions remain ephemeral and use `consume_content_item` for primary
content consumption. They preserve the Content Item type and resolve runtime
duration by preferring known duration over the existing summary heuristic.
Content Items and Recommendation Events remain durable. New events use the new
action name; historical `read_content_item` events are untouched. The event
action column already permits both, so it requires no migration or constraint.

Expose type/duration in Content Items API and type in Recommendation API.
Frontend types share the content-type union and the recommendation card accepts
both action names. Ordinary article presentation and controls remain unchanged.

## Consequences

- Ranking weights, lexical relevance, recency, duration-fit formula, diversity
  suppression, ownership, ordering, dispositions, and source health are unchanged.
- There are no new dependencies, infrastructure resources, ingestion pipelines,
  embedding calls, or type-specific presentation rules.
- Migrate the database before updated readers/writers. Deploy frontend support
  for both action names before the new recommendation backend. Deploy Writer
  before the extended RSS Fetch producer; older Writer versions reject the new
  message fields. Updated Writer accepts older queued messages.
- Podcast Lane A can classify/ingest `podcast_episode` and supply known duration
  using the existing source and writer contracts. Metadata and presentation are
  owned by that lane; no schema redesign is required for basic podcast support.
- Semantic-Relevance Lane B can evolve relevance independently using generic
  candidates without renaming the shared action or adding content-type weights.
- Likely future metadata includes episode/enclosure identity and host, video
  channel, DOI/journal/author, and ISBN/page count. Model those only when a
  concrete ingestion or presentation requirement justifies them.
- No unresolved shared-contract decisions remain for these two lanes.
