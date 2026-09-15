import json
import logging

from nrt_backend.content_items.repository import ContentItemRepository


logger = logging.getLogger(__name__)


def handler(event, context):
    if _http_method(event) != "GET":
        return _json_response(405, {"message": "Method not allowed"})

    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    try:
        content_items = ContentItemRepository().list_for_user(user_id)
    except Exception:
        logger.exception("Content Item listing failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(200, {"content_items": content_items})


def _http_method(event):
    return (
        event
        .get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", ""))
    )


def _authenticated_sub(event):
    return (
        event
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
        .get("sub")
    )


def _json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
