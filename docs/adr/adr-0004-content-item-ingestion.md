# ADR-0004: Durable Content Item Ingestion Uses SQS and a Writer Lambda

## Status

Accepted

## Context

Content Items are discovered asynchronously and must be persisted reliably
without coupling future RSS polling directly to Aurora. Duplicate discovery is
expected, and each Content Item must belong to the User who owns its Content
Source. The initial ingestion milestone must avoid new fixed-cost resources.

## Decision

The `ingestion` CloudFormation stack owns one standard SQS queue named
`nrt-<environment>-normalized-content-items` and one VPC-attached Content Item
Writer Lambda. The Lambda uses the existing private subnets, Lambda security
group, Aurora cluster, database secret, and Secrets Manager VPC endpoint.

The Writer validates each SQS JSON body, then uses one parameterized
`INSERT ... SELECT ... ON CONFLICT DO NOTHING` statement. The `SELECT` scopes
the source by both `content_source_id` and `user_id`, and the conflict target is
`(content_source_id, external_id)`. This makes duplicate deliveries successful
and prevents cross-user source association.

The event-source mapping enables `ReportBatchItemFailures`, uses a batch size of
five, and caps concurrency at two. Transient failures are returned as individual
batch failures for SQS retry. Permanently malformed and ownership-invalid
messages are safely logged and acknowledged. There is deliberately no DLQ in
this initial milestone.

An EventBridge rule invokes a VPC-attached Source Dispatch Lambda every 15
minutes. It selects active RSS Content Sources and publishes a minimal fetch job
to a second standard SQS queue. A non-VPC RSS Fetch Lambda consumes that queue,
retrieves public RSS/Atom feeds, and publishes normalized Content Item messages
to the existing queue. Keeping the fetcher outside the VPC provides public
internet access without adding a NAT Gateway; it receives no database or
Secrets Manager permissions.

## Consequences

- Ingestion is durable and pay-per-use, adding only SQS, Lambda, IAM, and its
  event-source mapping.
- Future producers publish the documented normalized message contract without
  needing database connectivity.
- Permanent-message investigation initially relies on CloudWatch logs because
  no DLQ is provisioned.
- The ingestion stack is deployed only when `ENABLE_DATABASE_BACKEND=true`.
- Polling deliberately emits repeat feed entries; Writer uniqueness remains the
  idempotency boundary until feed-state optimization is justified.
