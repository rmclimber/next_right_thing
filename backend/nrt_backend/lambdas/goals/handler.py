import base64
import binascii
from datetime import date
import json
import logging
import re

from nrt_backend.goals.repository import GoalNotFoundError, GoalRepository, GoalUpdate, NewGoal


logger = logging.getLogger(__name__)

DISALLOWED_CREATE_FIELDS = {
    "id",
    "user_id",
    "status",
    "created_at",
    "updated_at",
    "completed_at",
}
UPDATE_FIELDS = {"title", "description", "target_date", "status"}
STATUS_VALUES = {"active", "paused", "completed", "archived"}
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def handler(event, context):
    method = _http_method(event)

    if method == "POST":
        return _create_goal(event)

    if method == "GET":
        return _list_goals(event)

    if method == "PATCH":
        return _update_goal(event)

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


def _update_goal(event):
    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    goal_id = _path_goal_id(event)

    if not goal_id:
        return _json_response(404, {"message": "Not found"})

    try:
        payload = _json_body(event)
        goal_update = _validate_update_payload(payload)
    except ValueError as error:
        return _json_response(400, {"message": str(error)})

    try:
        goal = GoalRepository().update_for_user(goal_id, user_id, goal_update)
    except GoalNotFoundError:
        return _json_response(404, {"message": "Not found"})
    except Exception:
        logger.exception("Goal update failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(200, goal)


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


def _path_goal_id(event):
    path_parameters = event.get("pathParameters") or {}
    goal_id = path_parameters.get("id")

    if goal_id:
        return goal_id

    raw_path = event.get("rawPath") or event.get("path") or ""
    match = re.fullmatch(r"/goals/([^/]+)", raw_path)

    if match:
        return match.group(1)

    return None


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


def _validate_update_payload(payload):
    unsupported_fields = sorted(set(payload) - UPDATE_FIELDS)

    if unsupported_fields:
        raise ValueError("Request body contains fields that cannot be updated")

    if not payload:
        raise ValueError("Request body must contain at least one update field")

    values = {}

    if "title" in payload:
        title = payload["title"]

        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")

        values["title"] = title.strip()

    if "description" in payload:
        description = payload["description"]

        if description is not None and not isinstance(description, str):
            raise ValueError("description must be a string or null")

        values["description"] = description

    if "target_date" in payload:
        values["target_date"] = _validate_target_date(payload["target_date"])

    if "status" in payload:
        status = payload["status"]

        if status not in STATUS_VALUES:
            raise ValueError("status must be one of: active, archived, completed, paused")

        values["status"] = status

    if not values:
        raise ValueError("Request body must contain at least one update field")

    return GoalUpdate(values=values)


def _validate_target_date(target_date):
    if target_date is None:
        return None

    if not isinstance(target_date, str) or not ISO_DATE_PATTERN.match(target_date):
        raise ValueError("target_date must be a valid ISO date")

    try:
        return date.fromisoformat(target_date)
    except ValueError as error:
        raise ValueError("target_date must be a valid ISO date") from error


def _json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
