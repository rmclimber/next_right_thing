# ADR-0008: Opt-in semantic reranking of the bounded candidate pool

Status: Accepted. Automatic refresh is subsequently approved in ADR-0009.

## Context

Lexical Goal overlap misses related vocabulary. Recommendation eligibility is
already enforced in the database, and the selection pool contains at most 50
items. Request Lambdas have no configured Bedrock network access. This slice
must be reversible and must preserve baseline behavior on failure.

## Decision

Use precomputed, versioned, text-hashed embeddings in auxiliary PostgreSQL JSONB
tables and exact cosine reranking in the existing Recommendation Service. Start
with Titan Text Embeddings V2, 256 dimensions. Batch generation is explicitly
operator-run with an injectable provider; no request-time inference. Keep
baseline as the default; support shadow and semantic modes. Incomplete or invalid
coverage falls back for the whole pool. See the feature design for text and
score definitions. Add no AWS resources or runtime dependencies.

## Alternatives and consequences

pgvector can support future database retrieval but offers little benefit for
50 candidates and introduces an unverified extension prerequisite. A separate
vector database is unnecessary. Request-time inference adds latency, failure
modes, and network costs. External providers add credentials and data routing.

The cache is derived operational data, not a new domain relationship. Content
and Goal deletion cascades to cached vectors. Changed text invalidates vectors
immediately at read time. Batch refresh is required after new content/Goals;
until then baseline remains available. Candidate recall remains limited to the
latest eligible 50. Raw cosine is an initial heuristic, not calibrated relevance.
Automatic generation was subsequently reviewed and approved in ADR-0009.
Indexed retrieval and paid networking still require review before implementation.
No production quality claim follows from synthetic tests.
