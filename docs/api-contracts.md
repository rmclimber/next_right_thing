# API

## GET /me

Requires a valid Cognito access token in the `Authorization: Bearer <token>` header.
The token must include the `aws.cognito.signin.user.admin` scope.

Response:

```json
{
  "sub": "cognito-user-sub"
}
```
