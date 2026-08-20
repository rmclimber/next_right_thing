import json


def access_token_from(event):
    header = event.get("headers", {}).get("authorization", "")
    prefix = "Bearer "

    if header.startswith(prefix):
        return header[len(prefix):]

    return header


def handler(event, context):
    claims = (
        event
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    body = {
        "sub": claims.get("sub"),
    }

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
