# ADR-0003: Environment Database Backend Deployment Gate

## Status

Accepted

## Context

NRT has separate development and production environments. Development needs the
complete database-backed application path, while production may remain dormant
before production readiness to avoid unnecessary fixed Aurora and VPC endpoint
costs.

The GitHub Environment variable `ENABLE_DATABASE_BACKEND` is configured outside
the repository and is treated as an external deployment input.

## Decision

Deployments will pass `ENABLE_DATABASE_BACKEND` into the shared CloudFormation
stack on every run. The shared stack will always deploy, but the Secrets Manager
interface VPC endpoint and its dedicated endpoint security group will exist only
when the database backend is enabled.

When `ENABLE_DATABASE_BACKEND` is not `true`, the deployment workflow skips the
database stack, migration Lambda packaging and invocation, database-backed
application Lambda packaging, and API stack deployment. Authentication remains
independent, and frontend deployment continues to use the existing
`ENABLE_FRONTEND_HOSTING` gate.

The database stack exposes `DatabaseDeletionProtection`, which defaults to
`true`. Ordinary deployments do not disable deletion protection or delete
database stacks.

## Consequences

Development keeps the existing complete deployment behavior while
`ENABLE_DATABASE_BACKEND=true`.

Production can retain reproducible shared/auth/frontend infrastructure with the
database backend disabled. Existing database destruction remains an explicit
operator action and is not coupled to the deployment gate.
