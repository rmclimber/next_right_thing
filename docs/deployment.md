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
- CALLBACK_URL
- LOGOUT_URL
- CORS_ALLOWED_ORIGIN
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
api
```

using environment-specific stack names:

Development:

```
shared-dev
frontend-dev
auth-dev
database-dev
api-dev
```

Production:

```
shared-prod
frontend-prod
auth-prod
database-prod
api-prod
```

When `ENABLE_DATABASE_BACKEND` is not `true`, the `database-*` and `api-*`
stacks are not deployed by the workflow. The `shared-*` stack still deploys, but
omits only the Secrets Manager interface VPC endpoint and its dedicated endpoint
security group.

Resource names are similarly parameterized using `StackSuffix`.

The frontend stack provisions static hosting infrastructure only. It creates a
private S3 bucket, a CloudFront distribution, and a CloudFront Origin Access
Control (OAC) that allows CloudFront to read objects from the bucket. The bucket
does not use S3 static website hosting and is not publicly readable.

The frontend distribution currently uses the default CloudFront domain. The
stack outputs `FrontendBucketName`, `CloudFrontDistributionId`,
`CloudFrontDomainName`, and `FrontendUrl` for later deployment and configuration
work.

The frontend stack is deployed before the auth and API stacks so a later
milestone can use `FrontendUrl` for Cognito callback/logout URLs and API CORS.
Those settings remain controlled by the existing GitHub Environment variables
until that rewiring is explicitly implemented.

The API stack uses Lambda deployment packages uploaded to the artifact bucket
created by the corresponding shared stack. The `/me` package key is derived
from the Git commit SHA so repeated deployments do not accidentally reuse stale
Lambda code.

The database stack also deploys a dedicated migration Lambda. Its deployment
package includes `nrt_backend`, Alembic configuration, migration revisions, and
PostgreSQL runtime dependencies. The package key is derived from the Git commit
SHA.

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
