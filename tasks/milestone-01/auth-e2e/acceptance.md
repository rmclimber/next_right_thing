# Task 001: Acceptance Criteria

## Definition of Done

The task is complete when all of the following are true.

### Infrastructure

* Authentication stack is deployed.
* API stack is deployed.
* Required CloudFormation outputs are available.

### Application

* The Next.js application builds successfully.
* The application starts locally without errors.
* Authentication is performed using AWS Amplify.
* Cognito Hosted UI is used for sign in.
* Authorization Code + PKCE is used.
* Login succeeds.
* Logout succeeds.

### Protected Route

* An unauthenticated user cannot access the protected dashboard.
* An authenticated user is redirected to the dashboard after login.

### API

The dashboard successfully calls the protected `GET /me` endpoint.

The backend returns:

* `sub`
* `email`
* `email_verified`

The dashboard displays those values.

### Security

* No AWS identifiers are hardcoded.
* Authentication configuration is supplied via environment variables.
* API requests use the authenticated access token.
* The backend derives user identity from the validated JWT rather than trusting client-supplied identifiers.

### Manual Test Procedure

1. Start the Next.js application.
2. Open the application in a browser.
3. Click **Sign In**.
4. Authenticate through Cognito Hosted UI.
5. Return to the application.
6. Verify the dashboard loads.
7. Verify the authenticated identity is displayed.
8. Refresh the page.
9. Verify the session persists.
10. Click **Sign Out**.
11. Verify the protected dashboard is no longer accessible.

## Out of Scope

The following capabilities are intentionally excluded from this task:

* recommendations
* goals
* uploads
* reports
* content ingestion
* recommendation engine
* user preferences
* application navigation
* production UI polish
* monitoring
* analytics
* performance optimization

This task exists solely to validate the end-to-end authentication path before feature development begins.
