import base64
import binascii
from datetime import datetime, timezone
import json
import logging
import re
from uuid import UUID

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
        limit, filter, position = _list_request(event)
    except ValueError as error:
        return _json_response(400, {"message": str(error)})
    try:
        content_items, next_position = ContentItemRepository().list_for_user(
            user_id, limit=limit, filter=filter, position=position,
        )
    except Exception:
        logger.exception("Content Item listing failed")
        return _json_response(500, {"message": "Internal server error"})
    return _json_response(200, {
        "content_items": content_items,
        "next_cursor": _encode_cursor(next_position, filter) if next_position else None,
    })


# Position tokens are untrusted; ownership is always enforced independently in SQL.
def _encode_cursor(position, filter):
    discovered, created, item_id = position
    payload = {"v": 1, "filter": filter, "discovered_at": discovered.isoformat(),
               "created_at": created.isoformat(), "id": str(item_id)}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")


def _list_request(event):
    query = event.get("queryStringParameters") or {}
    limit = query.get("limit", "50")
    filter = query.get("filter", "all")
    if not isinstance(limit, str) or not re.fullmatch(r"[0-9]{1,3}", limit) or not 1 <= int(limit) <= 100:
        raise ValueError("limit must be an integer from 1 through 100")
    if not isinstance(filter, str) or filter not in {"all", "snoozed", "completed", "archived"}:
        raise ValueError("filter must be all, snoozed, completed, or archived")
    position = None
    if "cursor" in query:
        token = query["cursor"]
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 2048 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
                raise ValueError()
            def unique_object(pairs):
                result = dict(pairs)
                if len(result) != len(pairs):
                    raise ValueError()
                return result
            payload = json.loads(base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True), object_pairs_hook=unique_object)
            if not isinstance(payload, dict) or set(payload) != {"v", "filter", "discovered_at", "created_at", "id"}:
                raise ValueError()
            if type(payload["v"]) is not int or payload["v"] != 1 or payload["filter"] != filter:
                raise ValueError()
            timestamps = []
            for field in ("discovered_at", "created_at"):
                value = payload[field]
                # PostgreSQL timestamps have microsecond precision; never truncate input.
                if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value):
                    raise ValueError()
                timestamp = datetime.fromisoformat(value)
                if timestamp.utcoffset() is None:
                    raise ValueError()
                timestamps.append(timestamp.astimezone(timezone.utc))
            if not isinstance(payload["id"], str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", payload["id"]):
                raise ValueError()
            position = (*timestamps, UUID(payload["id"]))
        except (ValueError, TypeError, KeyError, binascii.Error, UnicodeDecodeError, RecursionError, OverflowError):
            raise ValueError("Invalid pagination cursor") from None
    return int(limit), filter, position


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
