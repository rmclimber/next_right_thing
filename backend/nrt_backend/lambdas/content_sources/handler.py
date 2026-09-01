import base64
import binascii
import json
import logging
import re
from urllib.parse import urlparse

from nrt_backend.content_sources.repository import (
    ContentSourceConflictError,
    ContentSourceNotFoundError,
    ContentSourceRepository,
    ContentSourceUpdate,
    NewContentSource,
)


logger = logging.getLogger(__name__)

DISALLOWED_CREATE_FIELDS = {
    "id",
    "user_id",
    "source_type",
    "status",
    "created_at",
    "updated_at",
}
UPDATE_FIELDS = {"name", "url", "status"}
STATUS_VALUES = {"active", "paused", "archived"}


def handler(event, context):
    method = _http_method(event)

    if method == "POST":
        return _create_content_source(event)

    if method == "GET":
        return _list_content_sources(event)

    if method == "PATCH":
        return _update_content_source(event)

    return _json_response(405, {"message": "Method not allowed"})


def _create_content_source(event):
    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    try:
        payload = _json_body(event)
        new_source = _validate_create_payload(payload)
    except ValueError as error:
        return _json_response(400, {"message": str(error)})

    try:
        source = ContentSourceRepository().create(user_id, new_source)
    except ContentSourceConflictError:
        return _json_response(409, {"message": "Content source URL already exists"})
    except Exception:
        logger.exception("Content source creation failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(201, source)


def _list_content_sources(event):
    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    try:
        sources = ContentSourceRepository().list_for_user(user_id)
    except Exception:
        logger.exception("Content source listing failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(200, {"content_sources": sources})


def _update_content_source(event):
    user_id = _authenticated_sub(event)

    if not user_id:
        return _json_response(401, {"message": "Unauthorized"})

    source_id = _path_content_source_id(event)

    if not source_id:
        return _json_response(404, {"message": "Not found"})

    try:
        payload = _json_body(event)
        source_update = _validate_update_payload(payload)
    except ValueError as error:
        return _json_response(400, {"message": str(error)})

    try:
        source = ContentSourceRepository().update_for_user(source_id, user_id, source_update)
    except ContentSourceNotFoundError:
        return _json_response(404, {"message": "Not found"})
    except ContentSourceConflictError:
        return _json_response(409, {"message": "Content source URL already exists"})
    except Exception:
        logger.exception("Content source update failed")
        return _json_response(500, {"message": "Internal server error"})

    return _json_response(200, source)


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


def _path_content_source_id(event):
    path_parameters = event.get("pathParameters") or {}
    source_id = path_parameters.get("id")

    if source_id:
        return source_id

    raw_path = event.get("rawPath") or event.get("path") or ""
    match = re.fullmatch(r"/content-sources/([^/]+)", raw_path)

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

    name = _validated_name(payload.get("name"))
    url = _validated_url(payload.get("url"))

    return NewContentSource(name=name, url=url)


def _validate_update_payload(payload):
    unsupported_fields = sorted(set(payload) - UPDATE_FIELDS)

    if unsupported_fields:
        raise ValueError("Request body contains fields that cannot be updated")

    if not payload:
        raise ValueError("Request body must contain at least one update field")

    values = {}

    if "name" in payload:
        values["name"] = _validated_name(payload["name"])

    if "url" in payload:
        values["url"] = _validated_url(payload["url"])

    if "status" in payload:
        status = payload["status"]

        if status not in STATUS_VALUES:
            raise ValueError("status must be one of: active, archived, paused")

        values["status"] = status

    if not values:
        raise ValueError("Request body must contain at least one update field")

    return ContentSourceUpdate(values=values)


def _validated_name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")

    return name.strip()


def _validated_url(url):
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    trimmed_url = url.strip()

    if any(character.isspace() for character in trimmed_url):
        raise ValueError("url must be a valid HTTP or HTTPS URL")

    parsed_url = urlparse(trimmed_url)

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("url must be a valid HTTP or HTTPS URL")

    return trimmed_url


def _json_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }
