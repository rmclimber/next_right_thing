
## Overview:
Frontend:
- Next.js

API:
- Lambda + API Gateway

Background jobs:
- Lambda (RSS ingestion and scheduled embedding refresh)
- ECS/Fargate (future long-running jobs)

DB:
- Aurora PostgreSQL

Storage:
- S3

Auth:
- Cognito

## Components

### Frontend (Next.js)

Responsibilities:

- User authentication
- User interface
- Local application state
- Calling backend APIs

Does not:

- Contain business logic
- Access databases directly

Hosting:

- The frontend is statically exported by Next.js.
- CloudFront serves the exported files from a private S3 bucket.
- CloudFront accesses S3 through Origin Access Control (OAC).
- The S3 bucket is not configured for public access or S3 static website hosting.
- Development and production use separate `frontend-dev` and `frontend-prod` stacks.
- The application currently uses default CloudFront domains; no custom domain, Route 53 record, or ACM certificate is configured.

---

### API

Responsibilities:

- Authentication/authorization
- CRUD operations
- API validation
- Coordination between frontend and backend services

Does not:

- Perform recommendation ranking
- Run scheduled jobs

---

### Recommendation Service

Responsibilities:

- Generate recommendations
- Apply ranking algorithms
- Incorporate user preferences
- Produce recommendation explanations

The initial service is invoked synchronously by the authenticated
`GET /recommendations/next` API Lambda. It loads bounded, user-scoped Content
Items and active Goals from Aurora, derives ephemeral Candidate Actions, ranks
them deterministically, and persists only the selected Recommendation Event.
Content Items are generic durable content with a constrained `content_type` and
nullable known `duration_minutes`. Candidate Actions are ephemeral and use
`consume_content_item`, preserving the item type. Recommendation Events are
durable; historical `read_content_item` decisions remain unchanged. The
recommendation response adds the item type; ranking weights, lexical relevance,
recency, diversity suppression, and disposition eligibility remain unchanged.

Its Lambda uses JSON application logs at `INFO` for the bounded candidate, Goal
count, selection, and event-persistence operational messages; Lambda system
logs remain at `WARN`.

The deterministic v1 score is `0.40 * recency + 0.35 * goal relevance + 0.25
* duration fit`, with each component bounded from 0 to 1. Recency is 1.0 for
items under one day old, 0.7 under seven days, 0.4 under 30 days, and 0.1
otherwise, using `published_at` or `discovered_at` as a fallback. Goal relevance
is lexical overlap between normalized title/summary and active Goal
title/description tokens. Candidate duration first uses Content Item
`duration_minutes` when known. Otherwise, reading duration uses summary word count at 225 words
per minute, with a five-minute minimum because feed summaries are often
truncated excerpts. A fitting item
scores from 0.5 to 1.0 according to how closely it fills the time window; an
item up to 25% over scores 0.25, and longer items score zero. Ties sort by
total score descending, then `discovered_at` descending, `created_at`
descending, and Content Item ID ascending.
Candidate selection excludes Content Items whose user state is completed,
archived, or actively snoozed until a future time. This eligibility filtering is
performed in the bounded Aurora query; expired snoozes become eligible without a
background job.

Semantic relevance is an opt-in reranking layer (ADR-0008). The default
`baseline` mode retains the deterministic v1 ranking. `shadow` compares cached
semantic and baseline rankings while serving baseline; `semantic` replaces only
the Goal relevance component with maximum nonnegative cosine similarity to an
active Goal. Eligibility, the 50-item bound, diversity suppression, recency,
duration fit, and tie-breaking are unchanged. Incomplete, stale, invalid, or
unavailable embeddings fall back to the entire baseline ranking. Requests never
invoke an embedding provider. Derived, model/version/text-hashed vectors live in
auxiliary PostgreSQL JSONB tables and are refreshed by explicit batch tooling
using Titan Text Embeddings V2 (256 dimensions). Exact similarity over this small
pool requires no database extension. A non-VPC embedding-refresh Lambda uses
RDS Data API and Bedrock every two hours (ADR-0009). It reuses these caches and
the same text/hash/provider logic; see `docs/features/semantic-relevance/operations.md`.

Does not:

- Render UI
- Manage authentication

---

### Background Workers

Responsibilities:

- Poll content sources
- Parse content
- Extract metadata
- Update search indexes
- Generate embeddings (two-hour scheduled Lambda and explicit operator batch)

RSS ingestion uses a private-source/public-fetch/private-write pipeline:

```
Aurora Content Sources
    ↓ RDS Data API
Source Dispatch Lambda (non-VPC)
    ↓
rss-fetch-jobs SQS
    ↓
RSS Fetch Lambda (outside the VPC)
    ├── RDS Data API → Aurora Content Sources (source-health update)
    └── normalized-content-items SQS
          ↓
    Content Item Writer Lambda (VPC-attached)
          ↓
    Aurora Content Items
```

Source Dispatch is a targeted non-VPC exception: it uses the RDS Data API for
its simple active-RSS-source read, then sends fetch jobs to SQS through
AWS-managed networking. The Content Item Writer remains VPC-attached and uses
psycopg with the Aurora endpoint and Secrets Manager credentials. The RSS Fetch
Lambda has no VPC configuration or database access, so it can reach public
feeds without a NAT Gateway. RSS Fetch additionally uses the RDS Data API for
one lightweight, ownership-scoped Content Source health update after each
fetch/parse outcome; application APIs and Writer database access remain psycopg
over the VPC. The normalized message contract is documented in
`docs/content-item-ingestion.md`. `ContentSource.source_type` identifies the
acquisition mechanism/provider; `ContentItem.content_type` identifies the item
kind. Ordinary RSS entries omit type/duration fields; Writer defaults them to
`article`/`null` and does no type inference. RSS Fetch's encapsulated podcast
parser identifies entries with usable HTTP(S) audio enclosures and emits
`podcast_episode` with nullable known duration into the same queue. The common
item URL is the audio enclosure for external listening. Source registration,
dispatch, Writer, persistence, and recommendation backend contracts are reused
without new resources or migrations. See ADR-0007 for the shared contract and
`docs/features/podcast-support/spec.md` for podcast behavior and rollout.

---

### Automatic Embedding Refresh

Automatic embedding refresh is another targeted non-VPC Data API exception. A
dedicated Lambda discovers users from existing Content Items and active Goals,
scans bounded pages, and skips valid current vectors. It uses regional Titan V2
and writes only auxiliary embedding caches through ownership-scoped SQL. Long
source text is transferred in bounded chunks without changing the embedding
representation. Transient retries, a per-invocation generation budget, and a
deadline reserve bound work; failures or incomplete sweeps emit a summary and
fail the invocation, preserving successful writes for retry. The ingestion stack
defines its EventBridge Scheduler schedule, scoped roles, 14-day log group,
asynchronous retry configuration, and Errors alarm. No new VPC endpoint, NAT,
queue, or schema is required. Application APIs and Writer continue using psycopg.

### Database

Responsibilities:

- Persistent application state
- Application schema version tracking through Alembic migrations

CloudFormation manages the Aurora PostgreSQL infrastructure. PostgreSQL
application schema changes are managed separately by versioned Alembic
migrations in the backend project.

Database-backed application infrastructure can be disabled per deployment
environment through the externally configured GitHub Environment variable
`ENABLE_DATABASE_BACKEND`. Development currently enables the database backend so
the complete application path is deployed. Production may keep only the
shared/auth/frontend foundation before production readiness; disabling the gate
skips the database, migrations, and database-backed API deployment without
destroying an existing database stack.

### Database Migrations

Responsibilities:

- Apply versioned PostgreSQL schema migrations
- Run inside the shared VPC using the Lambda database security group
- Use Secrets Manager for database credentials

Database migrations are executed by a dedicated invocation-only Lambda during
environment deployment. The migration Lambda is not attached to API Gateway and
is not part of normal application request handling.

## Data Flow
### Example 1
User requests recommendations

Browser
    ↓
API
    ↓
Recommendation Service
    ↓
PostgreSQL
    ↓
Recommendation
    ↓
Browser

### Example 2:
Content Item persistence

Normalized Content Item message
    ↓
SQS
    ↓
Content Item Writer Lambda
    ↓
PostgreSQL

## Architectural Constraints

- Frontend never accesses the database directly.
- Business logic resides in backend services.
- Recommendation generation is isolated from API request handling.
- API contracts are the only communication mechanism between frontend and backend.
- Shared domain types live in `/packages/shared`.
- Infrastructure is managed declaratively.

## Principles
- Prefer deterministic systems over AI when they achieve comparable user value.

## Source of Truth

The following documents define the system:

- `vision.md` defines the product mission.
- `domain-model.md` defines the business concepts.
- `architecture.md` defines system organization.
- Feature specifications define expected behavior.
- Source code implements the behavior described by those documents.

If implementation and documentation diverge, either the code or the documentation should be updated so they remain consistent.
