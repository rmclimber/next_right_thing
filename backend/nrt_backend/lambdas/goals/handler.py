import base64
import binascii
from datetime import date
import json
import logging
import re

from nrt_backend.goals.repository import GoalRepository, NewGoal


logger = logging.getLogger(__name__)

DISALLOWED_CREATE_FIELDS = {
    "id",
    "user_id",
    "status",
    "created_at",
    "updated_at",
    "completed_at",
}
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def handler(event, context):
    method = _http_method(event)

    if method == "POST":
        return _create_goal(event)

    if method == "GET":
        return _list_goals(event)

    return _json_response(405, {"message": "Method not allowed"})


def _create_goal(event):
    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    try:
        payload = _json_body(event)
        new_goal = _validate_create_payload(payload)
    except ValueError as error:
        return _json_response(400, {"message": str(error)})

    try:
        goal = GoalRepository().create(user_id, new_goal)
    except Exception:
        logger.exception("Goal creation failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(201, goal)


def _list_goals(event):
    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    try:
        goals = GoalRepository().list_for_user(user_id)
    except Exception:
        logger.exception("Goal listing failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(200, {"goals": goals})


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


def _json_body(event):
    body = event.get("body")

    if body is None:
        raise ValueError("Request body must be valid JSON")

    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as error:
            raise ValueError("Request body must be valid JSON") from error

    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("Request body must be valid JSON") from error

    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    return payload


def _validate_create_payload(payload):
    disallowed_fields = sorted(DISALLOWED_CREATE_FIELDS.intersection(payload))

    if disallowed_fields:
        raise ValueError("Request body contains fields that cannot be set")

    title = payload.get("title")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")

    description = payload.get("description")

    if description is not None and not isinstance(description, str):
        raise ValueError("description must be a string when supplied")

    target_date = payload.get("target_date")

    if target_date is not None:
        if not isinstance(target_date, str) or not ISO_DATE_PATTERN.match(target_date):
            raise ValueError("target_date must be a valid ISO date")

        try:
            target_date = date.fromisoformat(target_date)
        except ValueError as error:
            raise ValueError("target_date must be a valid ISO date") from error

    return NewGoal(
        title=title.strip(),
        description=description,
        target_date=target_date,
    )


def _json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
