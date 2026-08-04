# NRT Web

Minimal Next.js application for validating Cognito Hosted UI authentication and
the authenticated `GET /me` API endpoint.

## Configuration

Copy `.env.local.example` to `.env.local` and fill values from CloudFormation
outputs:

```text
NEXT_PUBLIC_AWS_REGION=us-west-2
NEXT_PUBLIC_COGNITO_USER_POOL_ID=<auth.UserPoolId>
NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID=<auth.UserPoolClientId>
NEXT_PUBLIC_COGNITO_DOMAIN=<auth.UserPoolDomain>
NEXT_PUBLIC_AUTH_REDIRECT_SIGN_IN=http://localhost:3000/dashboard
NEXT_PUBLIC_AUTH_REDIRECT_SIGN_OUT=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=<api.ApiEndpoint>
```

`NEXT_PUBLIC_COGNITO_DOMAIN` may include or omit `https://`.

## Run Locally

```bash
pnpm install
pnpm dev
```

Then open `http://localhost:3000`, sign in, and verify that the dashboard
displays `email`, `sub`, and `email_verified`.
