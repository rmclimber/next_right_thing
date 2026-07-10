# Engineering Workflow

## Principles

- Infrastructure is defined as code.
- AI agents generate infrastructure code.
- Infrastructure is deployed via CloudFormation.
- Manual AWS console changes are temporary and must be reflected in code.
- Production changes occur through pull requests.

## Expected Workflow

1. Update design documents.
2. Update feature specification.
3. Implement code.
4. Update tests.
5. Deploy through CloudFormation.
6. Update documentation if behavior changed.

## AWS

AI agents should:

- Modify CloudFormation templates.
- Never assume resources exist unless defined in the repository.
- Never depend on manual console configuration.