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

# Testing Philosophy

The purpose of testing is to verify observable system behavior, not implementation details.

## Guiding Principles

* Prefer testing behavior over implementation.
* Write tests that remain valid after internal refactoring.
* Favor integration tests over excessive mocking.
* End-to-end user workflows are the highest-confidence tests.
* Every reported bug should result in a regression test whenever practical.

## Test Pyramid

### Unit Tests

Verify isolated business logic.

Examples:

* recommendation scoring
* feed parsing
* validation
* utility functions

### Integration Tests

Verify communication between components.

Examples:

* API endpoints
* database persistence
* background worker execution
* authentication

### End-to-End Tests

Verify complete user workflows.

Examples:

* Sign in
* Add a content source
* Receive a recommendation
* Complete or dismiss a recommendation

## Feature Test Plans

Every significant feature should include a `test-plan.md` describing expected behavior using:

* Given
* When
* Then

These behavioral specifications serve as the basis for automated tests.

# Definition of Done

A feature is considered complete only when all of the following are true.

## Implementation

* Acceptance criteria are satisfied.
* Code follows the documented architecture.
* No unnecessary complexity has been introduced.
* Public APIs are documented.

## Testing

* Relevant unit tests have been added or updated.
* Integration tests pass.
* End-to-end tests are updated when user workflows change.
* Existing test suite passes.

## Documentation

* Feature documentation reflects current behavior.
* Design documents have been updated if the implementation required architectural or domain changes.
* ADRs have been created for significant architectural decisions.

## Quality

* Linting passes.
* Type checking passes.
* Build succeeds.
* No unresolved TODOs remain without a linked issue or explicit justification.

## Review Checklist

Before marking a feature complete, ask:

* Does this align with the product vision?
* Does it preserve the domain model?
* Does it respect the architectural constraints?
* Is it the simplest solution that satisfies the requirements?
* Would another engineer understand this change six months from now?
