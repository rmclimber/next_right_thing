import json
import logging

from nrt_backend.shared.database import connect


logger = logging.getLogger(__name__)


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
    sub = claims.get("sub")

    connection = None

    try:
        logger.warning("Starting database connectivity smoke test")
        connection = connect()
        logger.warning("Database connection established; executing smoke query")

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
        logger.warning("Database connectivity smoke test succeeded")
    except Exception:
        logger.exception("Database connectivity smoke test failed")

        return {
            "statusCode": 500,
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"message": "Internal server error"}),
        }
    finally:
        if connection is not None:
            connection.close()

    body = {
        "sub": sub,
        "database": {
            "connected": True,
        },
    }

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
