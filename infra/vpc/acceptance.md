# Acceptance Criteria: Shared VPC Networking

- [ ] `infra/shared/shared.yaml` still provisions the existing
      `ArtifactBucket`.
- [ ] The shared stack provisions exactly one VPC.
- [ ] The VPC has DNS support and DNS hostnames enabled.
- [ ] Two private subnets exist in different Availability Zones.
- [ ] Each private subnet is associated with the private route table.
- [ ] No Internet Gateway is created.
- [ ] No NAT Gateway is created.
- [ ] No public subnet is created.
- [ ] No VPC endpoint is created.
- [ ] A security group exists for database access.
- [ ] The database security group does not allow unrestricted inbound
      PostgreSQL access.
- [ ] The stack outputs the VPC ID.
- [ ] The stack outputs both private subnet IDs.
- [ ] The stack outputs the database security group ID.
- [ ] The template works with the existing `shared-${STACK_SUFFIX}`
      deployment workflow.
- [ ] Development deployment succeeds.
- [ ] Existing auth and API infrastructure is unaffected.
- [ ] No unrelated files or infrastructure are changed.