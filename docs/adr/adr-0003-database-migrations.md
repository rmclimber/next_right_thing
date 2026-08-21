# ADR-0003: Database Schema Migrations Run Through Alembic Lambda

## Status

Accepted

## Context

NRT stores persistent application state in Aurora PostgreSQL. CloudFormation can
create and configure the database infrastructure, but it should not manage the
PostgreSQL application schema directly.

Schema changes need to be repeatable per environment, private to the VPC, and
able to fail deployment when they cannot be applied.

## Decision

NRT will manage PostgreSQL application schema with Alembic migrations stored in
the backend project.

A dedicated migration Lambda will run inside the existing private subnets using
the existing Lambda security group. It will read database connection settings
from environment variables and retrieve credentials from the database secret in
Secrets Manager.

GitHub Actions will package and deploy the migration Lambda with the database
stack, then invoke it synchronously after the database stack deploys.

The migration Lambda will not have an API Gateway route or public endpoint.

## Consequences

- CloudFormation remains responsible for Aurora infrastructure.
- Alembic becomes the source of truth for PostgreSQL application schema
  revisions.
- Migration failures stop environment deployment.
- Development and production migrations run independently against their own
  databases.
- Lambda packaging must include Alembic configuration, migration revisions, and
  runtime database dependencies.
