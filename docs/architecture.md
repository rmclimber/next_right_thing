
## Overview:
Frontend:
- Next.js

API:
- Lambda + API Gateway

Background jobs:
- ECS/Fargate

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
- Generate embeddings (future)

---

### Database

Responsibilities:

- Persistent application state
- Application schema version tracking through Alembic migrations

CloudFormation manages the Aurora PostgreSQL infrastructure. PostgreSQL
application schema changes are managed separately by versioned Alembic
migrations in the backend project.

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
Scheduled poll

EventBridge
    ↓
Worker
    ↓
RSS Feed
    ↓
Parser
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
