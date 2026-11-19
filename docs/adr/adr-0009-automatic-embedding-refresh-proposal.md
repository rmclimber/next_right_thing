# ADR-0009: Automatic embedding refresh with a scheduled non-VPC Lambda

Status: **Accepted — user approved 2026-11-18; implemented locally, not deployed.**

Date: 2026-11-18

## Context

ADR-0008 introduced an operator-run, injectable embedding refresh tool and
opt-in semantic ranking. Requests read cached vectors and retain the complete
baseline when coverage is incomplete. Automatic generation remains undecided.

Repository inspection confirms:

- Aurora Serverless v2 is private, with `EnableHttpEndpoint: true` and a default
  minimum of zero ACUs. Actual environment overrides and pause behavior are unverified.
- Source Dispatch and RSS Fetch health updates already use non-VPC Lambdas and
  RDS Data API (ADRs 0005 and 0006).
- Private subnets have a Secrets Manager endpoint, but no NAT Gateway or Bedrock
  runtime endpoint. Source Dispatch runs every 120 minutes.
- Embedding refresh currently uses psycopg through `EmbeddingRepository`. A
  Data API adapter is required; a scheduler alone cannot run that repository
  outside the VPC.

## Decision

Add one dedicated non-VPC embedding-refresh Lambda, invoked every two hours by
EventBridge Scheduler. It reads owned Content Items and active Goals through
RDS Data API, uses the existing versioned text/hash/provider functions, calls
Titan Text Embeddings V2, and upserts only the auxiliary embedding caches.

This extends the existing targeted Data API exception to one background task.
Application APIs, recommendation requests, Writer, and migrations keep their
existing database access. Aurora stays private. Do not change podcast ingestion
or attach another consumer to the normalized-content SQS queue.

Start with a two-hour cadence matching ingestion's current frequency. A new or
edited Goal can therefore use baseline for approximately two hours plus worker
runtime; this is a proposed tradeoff, not an existing freshness guarantee. The
same job supports an explicit one-off backfill invocation.

## Alternatives

Illustrative USD list prices use US East reference rates, 730 hours/month for
always-on networking, and exclude shared existing resources, tax, and credits.
Actual deployment region/prices must be confirmed before deployment.

| Option | Additional components beyond worker/schedule | Fixed incremental network cost/month | Assessment |
| --- | --- | --- | --- |
| Non-VPC Lambda + Data API | Data API repository adapter; scoped IAM | $0 | Recommended. Matches existing access pattern; modest adapter work. |
| Private Lambda + Bedrock interface endpoint | `bedrock-runtime` interface endpoint, endpoint policy and security group; existing private subnets/Secrets Manager endpoint reused | About $7.30 in one AZ or $14.60 in two AZs; plus $0.01/GB | Easiest reuse of psycopg refresh code, but adds a permanent network charge for a sparse job. One-AZ endpoint has reduced availability and may incur cross-AZ transfer. |
| Private Lambda + NAT | NAT Gateway, public subnet/route/Internet Gateway plumbing, public IPv4 address; existing private route tables need changes | About $36.50 per NAT/AZ including one IPv4 address, or $73 for two; plus $0.045/GB and applicable transfer | Useful for broad outbound access, excessive for Bedrock alone. |
| Non-VPC coordinator + private database Lambda | A second Lambda and invoke permissions; private DB function serves bounded fetch/save operations | $0 network floor; extra Lambda invocations/runtime | Preserves psycopg without an endpoint, but introduces orchestration and another function boundary despite existing Data API precedent. |

Endpoint arithmetic: $0.01/hour/AZ. NAT arithmetic: ($0.045 gateway + $0.005
IPv4)/hour. Neither gateway nor endpoint is assumed to exist already. Only the
Bedrock **runtime** endpoint is needed for `InvokeModel`; a Bedrock control-plane
endpoint is unnecessary for this provider.

An event-driven SQS embedding queue can later reduce freshness delay and idle
scans, but requires separate post-commit notifications for Content Items and Goal
edits, delivery/reconciliation behavior, and additional resources. A second
consumer of the existing normalized-content queue would compete with Writer,
not fan out messages. Keep scheduled reconciliation first. ECS/Fargate or AWS
Batch would add task/image/network orchestration without a present long-running
or compute-intensive requirement.

## Resources and changes

Provision per enabled database environment, through CloudFormation:

1. One Python 3.12 embedding-refresh Lambda outside the VPC, initially 512 MB,
   five-minute timeout, reserved concurrency one; no provisioned concurrency.
2. One Lambda execution role: logging, `rds-data:ExecuteStatement` on the existing
   cluster, `secretsmanager:GetSecretValue` on its existing managed secret, and
   `bedrock:InvokeModel` on the regional Titan V2 model ARN. No new secret.
3. One EventBridge Scheduler schedule and its execution role, scoped to invoking
   that Lambda. Scheduler is AWS's recommended option for new schedules; leave
   the existing Source Dispatch rule unchanged.
4. One explicit CloudWatch log group with 14-day retention and one standard
   Lambda Errors alarm. Configure bounded asynchronous retries. Partial refresh
   failures are logged, then surfaced as invocation failure after successful
   subjects have been saved, so retries skip successes.
5. Deployment artifact packaging and an environment enable/disable parameter.
   Reuse the existing artifact bucket and deployment workflow.

No queue, Step Functions state machine, VPC endpoint, NAT Gateway, new database,
vector extension, or additional cache migration is required for this proposal.
The previously implemented cache migration is still a prerequisite.

IAM scopes AWS resources, not SQL statements or tenant rows. Reusing the current
database secret retains its database privileges; application SQL must enforce
ownership. Database-enforced table restrictions would require a dedicated DB
principal/grants, and potentially another managed secret, as a separate choice.

## Worker behavior

- Implement the existing repository contract with Data API, retaining the
  current text representation, model key, vector validation, and injectable
  provider. Preserve the CLI's psycopg implementation.
- Discover users from existing owned rows, then scan deterministic pages of
  Content Items and active Goals. Skip matching valid cached vectors. Avoid
  timestamp-only invalidation, which would miss representation/model changes.
- Use conservative byte-bounded pages: Data API has a 1 MiB response limit.
  SQL may bound returned text for transport, but must preserve exactly the
  current representation; do not truncate raw HTML before normalization/hash.
- Bound new provider calls and execution time, continue past individual failures,
  and record scanned/skipped/generated/failed/remaining work. Cover the initial
  small corpus in one run; surface persistent budget exhaustion for explicit
  larger backfill or a later queued design.
- Retry transient provider/Data API failures with bounded backoff, including
  database-resume responses. Never hold a DB transaction across model inference.
- Upsert parameterized JSONB through Data API and revalidate ownership. A
  concurrent text change is detected by the existing request-time hash check;
  the next sweep refreshes it.
- At-least-once retries can occasionally repeat paid inference if persistence
  fails after a successful model call. No exactly-once inference claim is made.
- Keep recommendation fallback and ranking-mode configuration unchanged. Disabling
  the schedule stops refresh; existing recommendations remain available.

## Ongoing cost estimate

Reference unit prices checked on the proposal date:

| Charge | Reference price |
| --- | --- |
| Titan Text Embeddings V2 on-demand input | $0.02 per million tokens |
| Lambda x86 duration | $0.0000166667 per GB-second; requests $0.20/million |
| Data API, initial usage tier | $0.35/million billed 32-KB request units |
| Secrets Manager access | $0.05/10,000 API calls; reuse existing secret storage |
| EventBridge Scheduler | 14 million monthly invocations included; $1/million beyond allowance |
| CloudWatch | About $0.10/standard one-metric alarm/month; log ingestion $0.50/GB, storage extra |

For an illustrative small corpus with **1,000 new/changed texts/month averaging
500 tokens**, **360 runs/month averaging 30 seconds at 512 MB**, **100,000 billed
Data API units**, **10,000 secret accesses**, **50 MB logs**, and one alarm:

- Model: 500,000 tokens * $0.02/million = **$0.01**.
- Lambda: 360 * 30 * 0.5 * $0.0000166667, plus requests = **about $0.09**.
- Data API: 100,000 * $0.35/million = **$0.035**.
- Secret accesses: **$0.05**.
- Scheduling: **$0** within its ongoing included allowance.
- Alarm/log ingestion: **about $0.125**.
- Subtotal: **about $0.31/month**, excluding incremental Aurora compute/I/O/vector
  storage, log storage, artifact storage, and any optional notifications/custom
  metrics/CloudTrail data events. Lambda/Data API/CloudWatch free allowances are
  not subtracted. This is a scenario, not measured NRT usage.

**Aurora wake-ups can dominate.** A Data API request resumes a paused writer.
As an example, 360 additional six-minute awake periods at 0.5 ACU and
$0.12/ACU-hour cost **$2.16/month**. This is neither a floor nor a cap: overlapping
ingestion/API activity could make incremental wake-up cost much smaller, while
higher resumed capacity or longer idle timeouts could make it larger. Existing
managed-secret storage, Aurora baseline charges, and the Secrets Manager endpoint
remain shared costs; they are not charged again as new resources here.

Avoid frequent polling initially. Measure actual `ServerlessDatabaseCapacity`,
Lambda Duration, request units, errors, and refresh backlog before increasing
frequency. Two independent two-hour schedules do not automatically share one
database wake period.

## Implementation and deployment boundary

The user approved this design and the two-hour cadence on 2026-11-18. The Data
API adapter, scheduled handler, infrastructure definitions, and deployment artifact
steps are implemented. Tests cover failures, retries, paging, idempotency,
ownership, budget limits, long text, and SQL/cache parity with PostgreSQL.

Sweeps restart from the beginning; successfully persisted current vectors are
skipped, so ordinary generation backlogs make progress across retries/runs.
Traversal cursors are not durably stored. A corpus whose scan alone exceeds the
time budget needs operator backfill or a later queued/checkpointed design.
Summary logs and Lambda Errors expose incomplete sweeps rather than silently
claiming completion. No work queue or automatic notification channel is added.

Deployment still requires separate explicit authorization. Bedrock access and
deployed-region behavior must be verified during that approved rollout. No AWS
CLI calls or live infrastructure changes were made during implementation.

## Sources

- [Aurora/Data API pricing](https://aws.amazon.com/rds/aurora/pricing/)
- [Aurora automatic pause/resume](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html)
- [Data API response limits](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/data-api.limitations.html)
- [AWS Titan V2 cost example](https://docs.aws.amazon.com/solutions/latest/generative-ai-application-builder-on-aws/cost.html)
- [Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [PrivateLink pricing](https://aws.amazon.com/privatelink/pricing/)
- [VPC/NAT/public IPv4 pricing](https://aws.amazon.com/vpc/pricing/)
- [Bedrock runtime VPC endpoints](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html)
- [EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/)
- [AWS recommendation for new schedules](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
- [Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/)
- [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
