ADR-0001: Infrastructure is managed exclusively through CloudFormation.
- Console changes are for emergency troubleshooting only.
- Permanent infrastructure changes must be reflected in CloudFormation.
- Every deployed resource should be reproducible from the repository.