# Objective: Add Shared VPC Networking

## Goal

Extend the existing `shared` CloudFormation stack with the minimal VPC
networking required by NRT's database architecture.

The VPC will provide private networking for Aurora PostgreSQL and for
Lambda functions that need to access the database.

## Scope

Modify the existing `infra/shared/shared.yaml`.

Add:

- One VPC.
- Two private subnets in different Availability Zones.
- A route table for the private subnets.
- An association between each private subnet and the private route table.
- A security group intended for database access.
- CloudFormation outputs for the VPC ID, private subnet IDs, and database
  security group ID.

The existing S3 ArtifactBucket must remain unchanged.

Do not add:

- Public subnets.
- Internet Gateway.
- NAT Gateway.
- VPC endpoints.
- RDS Proxy.
- Aurora resources.
- Lambda resources.
- Changes to auth or API infrastructure.

## Environment

The existing deployment workflow passes `StackSuffix` and deploys the
stack as `shared-${STACK_SUFFIX}`.

The VPC resources should therefore be reproducible independently in
development and production accounts.

## Design Constraints

- Use two Availability Zones in the configured AWS region.
- Use private RFC1918 address space.
- Do not hard-code an Availability Zone name such as `us-west-2a`;
  derive Availability Zones from the deployment region where practical.
- The database security group should not allow inbound PostgreSQL traffic
  from `0.0.0.0/0`.
- No internet access is required by the VPC at this stage.
- Follow the existing CloudFormation conventions in the repository.
- Do not modify unrelated infrastructure or documentation.

## Important

Read the existing repository documentation and CloudFormation templates
before making changes. In particular, use `docs/architecture.md`,
`docs/adr/adr-0001-infra.md`, and `docs/adr/adr-0002-database-networking.md`
as the architectural authority.

Do not redesign the architecture or introduce additional networking
components that are not required by this objective.