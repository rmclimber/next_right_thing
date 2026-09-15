# Deployment

## Overview

NRT uses trunk-based development with separate AWS accounts for development and production.

```
main
 │
 ▼
GitHub Actions
 │
 ▼
Development Account
 │
 └── automatic

workflow_dispatch
 │
 ▼
Manual Approval
 │
 ▼
Production Account
```

---

## AWS Accounts

Two AWS accounts are maintained.

| Account | Purpose |
|----------|---------|
| Development | Continuous integration and feature development |
| Production | Production deployments |

Resources are never shared between accounts.

---

## GitHub Actions

Deployment is performed using reusable GitHub Actions workflows.

Primary workflows:

```
.github/workflows/deploy.yml
.github/workflows/deploy-stack.yml
```

`deploy.yml` orchestrates deployments.

`deploy-stack.yml` performs a deployment for a single environment.

---

## Authentication

GitHub authenticates to AWS using OpenID Connect (OIDC).

No long-lived AWS credentials are stored in GitHub.

Each environment has:

- IAM Role
- GitHub Environment
- Environment-specific variables

---

## GitHub Environments

### Development

Deployment occurs automatically on every push to `main`.

Environment variables include:

- AWS_ROLE_ARN
- AWS_REGION
- STACK_SUFFIX
- CALLBACK_URL (used when frontend hosting is disabled)
- LOGOUT_URL (used when frontend hosting is disabled)
- CORS_ALLOWED_ORIGIN (used when frontend hosting is disabled)
- ENABLE_FRONTEND_HOSTING
- ENABLE_DATABASE_BACKEND

---

### Production

Production deployments are initiated using `workflow_dispatch`.

Deployment requires manual approval through GitHub Environments.

Production has its own independent configuration values.

`ENABLE_DATABASE_BACKEND` is configured outside the repository as a GitHub
Environment variable. Development currently sets it to `true`, which deploys
the complete shared, auth, database, migration, API, and optionally frontend
path. Production may set it to `false` before production readiness, which keeps
shared infrastructure, auth, and the existing frontend-hosting gate active while
skipping database, migration, and database-backed API deployment.

Disabling `ENABLE_DATABASE_BACKEND` does not delete an existing database stack
or change Aurora scaling settings. Database destruction remains an explicit
operator action outside the normal deployment workflow. The database template
keeps deletion protection enabled by default and exposes a parameter for
intentional operator-driven changes.

---

## CloudFormation Stacks

Each environment deploys:

```
shared
frontend
auth
database
ingestion
api
```

using environment-specific stack names:

Development:

```
shared-dev
frontend-dev
auth-dev
database-dev
ingestion-dev
api-dev
```

Production:

```
shared-prod
frontend-prod
auth-prod
database-prod
ingestion-prod
api-prod
```

When `ENABLE_DATABASE_BACKEND` is not `true`, the `database-*`, `ingestion-*`,
and `api-*` stacks are not deployed by the workflow. The `shared-*` stack still
deploys, but omits only the Secrets Manager interface VPC endpoint and its
dedicated endpoint security group.

Resource names are similarly parameterized using `StackSuffix`.

The frontend stack provisions static hosting infrastructure only. It creates a
private S3 bucket, a CloudFront distribution, and a CloudFront Origin Access
Control (OAC) that allows CloudFront to read objects from the bucket. The bucket
does not use S3 static website hosting and is not publicly readable.

The frontend distribution currently uses the default CloudFront domain. The
stack outputs `FrontendBucketName`, `CloudFrontDistributionId`,
`CloudFrontDomainName`, and `FrontendUrl` for later deployment and configuration
work.

When `ENABLE_FRONTEND_HOSTING` is `true`, the deployment workflow reads
`FrontendBucketName`, `CloudFrontDistributionId`, and `FrontendUrl` from the
environment's `frontend-*` CloudFormation stack rather than storing those
identifiers in GitHub Environment variables. It uses `FrontendUrl` as the
Cognito callback/logout and API CORS origin, then reads the auth and API stack
outputs needed for the static Next.js build. The workflow derives the public
build configuration from `AWS_REGION`, auth outputs, `ApiEndpoint`, and
`FrontendUrl`; it does not rely on CloudFront or S3 to inject configuration at
runtime. It installs the workspace's pnpm dependencies, runs `pnpm build` to
create the Next.js static export in `apps/web/out`, synchronizes the *contents*
of that directory to the root of the private frontend bucket with `aws s3 sync
--delete`, then invalidates `/*` on the discovered CloudFront distribution. The
workflow reports the discovered `FrontendUrl` after a successful upload and
invalidation.

When `ENABLE_FRONTEND_HOSTING` is not `true`, the frontend stack deployment,
frontend build, upload, and CloudFront invalidation steps are skipped. This
allows production frontend hosting to remain disabled independently of the
backend deployment gate.

The frontend stack is deployed before the auth and API stacks. For hosted
deployments, its `FrontendUrl` is used consistently as the API CORS origin, as
the Cognito logout URL, and with `/dashboard` appended as the Cognito callback
URL. When frontend hosting is disabled, the existing GitHub Environment
`CALLBACK_URL`, `LOGOUT_URL`, and `CORS_ALLOWED_ORIGIN` values continue to be
used for backend/auth deployment.

The API stack uses Lambda deployment packages uploaded to the artifact bucket
created by the corresponding shared stack. The `/me` package key is derived
from the Git commit SHA so repeated deployments do not accidentally reuse stale
Lambda code.

The database stack also deploys a dedicated migration Lambda. Its deployment
package includes `nrt_backend`, Alembic configuration, migration revisions, and
PostgreSQL runtime dependencies. The package key is derived from the Git commit
SHA.

The ingestion stack deploys the standard `nrt-<environment>-normalized-content-items`
SQS queue and a VPC-attached Content Item Writer Lambda. Its artifact uses the
same backend packaging pattern and is also keyed by Git commit SHA. The Writer
uses partial batch failures for transient database failures. Malformed messages
and messages whose Content Source is not owned by the supplied user are logged
without their payloads and acknowledged; this initial milestone has no DLQ.
The normalized message contract is documented in `docs/content-item-ingestion.md`.

After the database stack deploys, `deploy-stack.yml` invokes the migration
Lambda synchronously for the current `STACK_SUFFIX`. If Alembic fails, the
Lambda invocation fails and the environment deployment stops. Development and
production therefore run migrations against their own Aurora databases behind
their existing GitHub Environment boundaries.

CloudFormation manages Aurora infrastructure. PostgreSQL application schema is
managed by Alembic migrations under `backend/migrations`.

---

## Adding a New Stack

To add infrastructure:

1. Create a new CloudFormation template under `infra/`.
2. Add a deployment step to `deploy-stack.yml`.
3. Pass required parameters through GitHub Environment variables.
4. Verify successful deployment in development.
5. Promote to production using manual approval.

---

## Local Development

CloudFormation outputs are used to configure local development.

The primary values copied into `.env.local` are:

- Cognito User Pool ID
- Cognito Client ID
- Cognito Hosted UI Domain
- API URL

Whenever authentication infrastructure changes, regenerate these values before testing locally.

---

## Deployment Philosophy

Infrastructure should evolve only to support product features.

The project intentionally avoids speculative infrastructure.

New AWS services are introduced only when required by application functionality.
