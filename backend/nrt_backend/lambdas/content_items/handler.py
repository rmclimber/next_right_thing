import json
import logging

from nrt_backend.content_items.repository import ContentItemRepository
from nrt_backend.content_item_state.repository import (
    ContentItemNotFoundError,
    RecommendationEventValidationError,
)
from nrt_backend.content_item_state.service import ContentItemStateService


logger = logging.getLogger(__name__)


def handler(event, context):
    method = _http_method(event)
    if method == "GET":
        return _list_content_items(event)
    if method == "POST":
        return _apply_action(event)
    return _json_response(405, {"message": "Method not allowed"})


def _list_content_items(event):
    user_id = _authenticated_sub(event)
    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})
    try:
        content_items = ContentItemRepository().list_for_user(user_id)
    except Exception:
        logger.exception("Content Item listing failed")
        return _json_response(500, {"message": "Internal server error"})
    return _json_response(200, {"content_items": content_items})


def _apply_action(event):
    user_id = _authenticated_sub(event)
    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})
    try:
        content_item_id = (event.get("pathParameters") or {}).get("id")
        action, recommendation_event_id = _action_request(event)
        if not content_item_id:
            raise ValueError("Content Item id is required")
        state = ContentItemStateService().apply_action(user_id, content_item_id, action, recommendation_event_id)
    except ContentItemNotFoundError:
        return _json_response(404, {"message": "Content Item not found"})
    except (ValueError, RecommendationEventValidationError) as error:
        return _json_response(400, {"message": str(error)})
    except Exception:
        logger.exception("Content Item action failed")
        return _json_response(500, {"message": "Internal server error"})
    return _json_response(200, {"content_item_state": state})


def _action_request(event):
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Request body must be valid JSON")
    if not isinstance(body, dict) or set(body) - {"action", "recommendation_event_id"}:
        raise ValueError("Request body contains unsupported fields")
    action = body.get("action")
    if action not in {"snooze", "complete", "archive"}:
        raise ValueError("action must be one of snooze, complete, or archive")
    recommendation_event_id = body.get("recommendation_event_id")
    if recommendation_event_id is not None and not isinstance(recommendation_event_id, str):
        raise ValueError("recommendation_event_id must be a UUID string")
    return action, recommendation_event_id


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
