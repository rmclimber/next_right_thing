# ADR-0005: Source Dispatch Uses RDS Data API Outside the VPC

## Status

Accepted

## Context

Source Dispatch performs one simple read of active RSS Content Sources and then
sends a fetch job for each source to SQS. Its former psycopg connection required
private-subnet placement and direct retrieval of the Aurora database secret.
Those private subnets have neither a NAT Gateway nor an SQS interface VPC
endpoint, so the SQS send could time out.

Adding either network resource would introduce a fixed recurring cost for a
simple, scheduled read-and-dispatch workload.

## Decision

Aurora's RDS Data API is enabled declaratively on the existing private Aurora
PostgreSQL Serverless v2 cluster. Source Dispatch is a non-VPC Lambda and uses
`ExecuteStatement` with the cluster ARN, RDS-managed secret ARN, and database
name to query active RSS Content Sources. It receives scoped permission to
execute statements against that cluster, authorize Data API's use of the
managed secret, and send messages to the RSS fetch-jobs queue. It does not
retrieve or handle the database password.

The EventBridge schedule remains `rate(120 minutes)`.

This is intentionally a targeted exception. The Content Item Writer, APIs, and
migration Lambda remain VPC-attached and use psycopg with direct PostgreSQL
connectivity and the shared database credential helper.

## Consequences

- Source Dispatch can reach the RDS Data API and SQS through AWS-managed
  networking without a NAT Gateway or SQS interface VPC endpoint.
- Aurora remains private; enabling the Data API does not make it publicly
  accessible.
- Dispatch database access is explicitly distinct from transactional and
  application database access.
- Data API charges remain usage-based. No fixed-hourly network or compute
  resource is added.
- Broader migration to the Data API may be reconsidered if VPC/PrivateLink cost
  or operational complexity grows, but is not decided by this ADR.
