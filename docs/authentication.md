# Authentication

## Overview

NRT uses Amazon Cognito for authentication and authorization.

Authentication is performed entirely using the Cognito Hosted UI and the Amplify Auth client library. After authentication, API requests are authorized using JWT validation in API Gateway. Backend Lambda functions receive authenticated identity claims from API Gateway and never perform credential validation themselves.

The authentication architecture is intentionally simple:

```
Browser
    │
    ▼
Next.js + Amplify
    │
    ▼
Cognito Hosted UI
    │
    ▼
JWT Access Token
    │
    ▼
API Gateway JWT Authorizer
    │
    ▼
Lambda
```

---

## Components

### Next.js

The frontend uses Amplify Auth.

Responsibilities:

- Configure Amplify.
- Redirect users to the Cognito Hosted UI.
- Maintain the authenticated session.
- Attach bearer tokens to API requests.

The frontend never stores AWS credentials.

---

### Amazon Cognito

Each deployment environment has its own:

- User Pool
- App Client
- Hosted UI domain

For example:

| Environment | Hosted UI Domain |
|------------|------------------|
| Development | `https://nrt-dev-rmorris.auth.us-west-2.amazoncognito.com` |
| Production | production-specific domain |

User accounts are isolated between environments.

---

### API Gateway

API Gateway validates JWTs using a Cognito JWT Authorizer.

Validation includes:

- issuer
- audience (App Client)
- expiration
- signature

Only authenticated requests reach Lambda.

---

### Lambda

Lambda receives identity information from API Gateway in:

```
event.requestContext.authorizer.jwt.claims
```

Lambda trusts API Gateway's authentication and authorization decisions.

---

## OAuth Flow

NRT uses the OAuth 2.0 Authorization Code flow with PKCE.

High-level flow:

1. User clicks Sign In.
2. Amplify redirects to the Cognito Hosted UI.
3. User authenticates.
4. Cognito redirects back to the configured callback URL.
5. Amplify exchanges the authorization code for tokens.
6. Amplify stores the session.
7. Frontend calls protected APIs.

---

## Callback URL

The OAuth callback URL is:

```
http://localhost:3000/dashboard
```

This callback must exactly match the Callback URL configured on the Cognito App Client.

This is distinct from the logout URL.

---

## Environment Variables

Development requires:

```
NEXT_PUBLIC_AWS_REGION
NEXT_PUBLIC_COGNITO_USER_POOL_ID
NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID
NEXT_PUBLIC_COGNITO_DOMAIN
NEXT_PUBLIC_AUTH_REDIRECT_SIGN_IN
NEXT_PUBLIC_AUTH_REDIRECT_SIGN_OUT
NEXT_PUBLIC_API_BASE_URL
```

Values are obtained from CloudFormation stack outputs.

---

## Security Model

Authentication responsibilities are intentionally separated.

| Component | Responsibility |
|-----------|----------------|
| Cognito | Identity |
| Amplify | Client authentication |
| API Gateway | JWT validation |
| Lambda | Business logic |

This separation keeps authentication concerns out of application code.
