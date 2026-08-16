# ADR-0002: Database Networking and Persistence Infrastructure

## Status

Accepted

## Context

NRT requires persistent application state. The application architecture specifies PostgreSQL as the primary relational datastore, and Aurora PostgreSQL is the selected managed database service.

Aurora PostgreSQL requires a VPC. NRT currently has no VPC because its existing infrastructure—S3, Cognito, API Gateway, and Lambda—does not require application-managed VPC networking.

The first database-backed feature is expected to have low and variable traffic. The infrastructure should therefore minimize operational complexity and fixed cost while providing an appropriate security boundary for the database.

## Decision

NRT will use **Aurora PostgreSQL Serverless v2** for persistent application data.

A VPC will be introduced as shared infrastructure and will initially contain two private subnets across Availability Zones.

The initial networking architecture will be:

- The VPC is managed by the `shared` CloudFormation stack.
- Aurora is deployed in a separate `database` CloudFormation stack.
- Lambda functions that require database access will be attached to the VPC.
- Aurora will reside in private subnets and will not be directly accessible from the public internet.
- Aurora's security group will permit PostgreSQL access only from the security group assigned to authorized Lambda functions.
- Database credentials will be stored in AWS Secrets Manager rather than in source code, CloudFormation templates, or plaintext configuration.
- No public subnets will be created initially.
- No NAT Gateway will be created initially.
- No VPC endpoints will be created initially.

The initial environment structure will therefore be:

```text
Development Account
├── shared-dev
│   ├── S3
│   └── VPC
├── auth-dev
├── database-dev
│   └── Aurora PostgreSQL
└── api-dev
    └── Lambda + API Gateway
```

Production will use the corresponding `*-prod` stacks in the production AWS account.

## Rationale

Aurora PostgreSQL provides the relational data model, transactions, constraints, and query capabilities appropriate for NRT's domain.

Serverless v2 is preferred over provisioned Aurora because NRT is initially expected to have low and variable traffic. This allows database capacity to scale without requiring the project to provision for anticipated future load.

Private subnets provide an appropriate security boundary because application users do not need direct access to PostgreSQL. The intended access path is:

```text
Internet
    │
    ▼
API Gateway
    │
    ▼
Lambda
    │
    ▼
Aurora PostgreSQL
```

Lambda is therefore the application-facing component that requires database access.

The networking configuration intentionally avoids a NAT Gateway and VPC endpoints until a concrete requirement for outbound access from VPC-attached Lambda functions emerges. This avoids introducing additional infrastructure and recurring cost prematurely.

The database is kept in its own CloudFormation stack rather than the API stack so that database lifecycle and API deployment remain independently managed.

## Consequences

### Positive

- PostgreSQL provides a strong relational foundation for the NRT domain.
- Aurora is isolated from direct internet access.
- Database access can be restricted to authorized Lambda functions.
- Development and production databases are isolated by both AWS account and environment-specific stacks.
- The architecture avoids unnecessary networking infrastructure and fixed costs at the current scale.
- Database lifecycle is independent of API deployment.

### Negative

- Introducing Aurora requires application-managed VPC networking.
- Lambda functions that access Aurora become VPC-attached.
- Database connectivity is more operationally complex than the current API-only architecture.
- Additional infrastructure may be required if Lambda later needs broad outbound internet access or private connectivity to AWS services.
- Aurora Serverless v2 still incurs costs even at very low usage.

## Future Changes

The following are intentionally deferred until a concrete requirement emerges:

- RDS Proxy for connection pooling.
- NAT Gateway.
- VPC endpoints.
- Additional private subnets or more elaborate network segmentation.
- Separate database clusters for individual application domains.
- Database read replicas or other scaling infrastructure.

These may be introduced later without changing the fundamental decision to use Aurora PostgreSQL within a private VPC.