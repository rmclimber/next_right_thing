# Task 001: End-to-End Authentication

## Objective

Implement the thinnest possible Next.js frontend that proves the complete end-to-end authentication path.

This task exists to validate the platform infrastructure before implementing any NRT business functionality.

## Background

The repository already contains:

* project vision
* domain model
* architecture
* deployed AWS authentication infrastructure
* deployed API infrastructure

This task should build only the application code necessary to demonstrate that those components work together.

## Success Criteria

A user can:

1. Open the application.
2. Click **Sign In**.
3. Authenticate using the existing Cognito Hosted UI.
4. Return to the application.
5. Navigate to a protected dashboard page.
6. Call the existing authenticated `GET /me` endpoint.
7. Display the authenticated user's identity returned by the backend.

## Scope

Implement only the functionality necessary to satisfy the success criteria.

The implementation should include:

* Next.js frontend
* AWS Amplify authentication
* Cognito Hosted UI integration
* Authorization Code + PKCE flow
* Login
* Logout
* Protected dashboard page
* Authenticated call to `GET /me`
* Display of:

  * email
  * sub
  * email_verified

## Constraints

Do **not** implement any NRT business functionality.

Specifically exclude:

* recommendations
* goals
* learning plans
* uploads
* reports
* DynamoDB integration
* S3 integration
* Step Functions
* EventBridge
* recommendation engine
* navigation beyond what is required

Avoid introducing abstractions that are not justified by the current implementation.

## Configuration

Use the existing CloudFormation outputs from the deployed authentication and API stacks.

Do not hardcode AWS identifiers.

The application should obtain its configuration from environment variables.

## Deliverable

A developer should be able to:

1. Clone the repository.
2. Configure the required environment variables.
3. Run the Next.js application locally.
4. Authenticate with Cognito.
5. Successfully call the protected `GET /me` endpoint.

Completion of this task establishes the foundation for implementation of the first NRT feature.
