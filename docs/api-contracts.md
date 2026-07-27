# API

## GET /me

Requires a valid Cognito JWT in the `Authorization: Bearer <token>` header.

Response:

```json
{
  "sub": "cognito-user-sub",
  "email": "user@example.com",
  "email_verified": "true"
}
```
