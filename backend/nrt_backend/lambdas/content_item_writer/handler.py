import json
import logging
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from nrt_backend.content_items.repository import (
    CONTENT_TYPES,
    ContentItemRepository,
    ContentSourceOwnershipError,
    NewContentItem,
)


logger = logging.getLogger(__name__)

MESSAGE_FIELDS = {
    "user_id",
    "content_source_id",
    "external_id",
    "title",
    "url",
    "summary",
    "published_at",
    "discovered_at",
    "content_type",
    "duration_minutes",
}


def handler(event, context):
    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            item = _content_item_from_record(record)
            ContentItemRepository().create(item)
        except (ValueError, ContentSourceOwnershipError) as error:
            # Permanent errors are deliberately acknowledged. There is no DLQ yet.
            logger.warning("Content Item message rejected (%s): %s", message_id, error)
        except Exception:
            logger.exception("Content Item persistence failed (%s)", message_id)
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}


def _content_item_from_record(record):
    body = record.get("body")
    try:
        payload = json.loads(body)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("body must be valid JSON") from error

    if not isinstance(payload, dict):
        raise ValueError("body must be a JSON object")

    unsupported_fields = set(payload) - MESSAGE_FIELDS
    if unsupported_fields:
        raise ValueError("body contains unsupported fields")

    return NewContentItem(
        user_id=_required_string(payload, "user_id"),
        content_source_id=_uuid(payload.get("content_source_id")),
        external_id=_required_string(payload, "external_id"),
        title=_required_string(payload, "title"),
        url=_http_url(payload.get("url")),
        summary=_optional_string(payload, "summary"),
        published_at=_optional_timestamp(payload, "published_at"),
        discovered_at=_timestamp(payload.get("discovered_at"), "discovered_at"),
        content_type=_content_type(payload),
        duration_minutes=_duration_minutes(payload),
    )


def _content_type(payload):
    value = payload.get("content_type", "article")
    if not isinstance(value, str) or value not in CONTENT_TYPES:
        raise ValueError("content_type must be article, podcast_episode, video, research_article, or book")
    return value


def _duration_minutes(payload):
    value = payload.get("duration_minutes")
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        raise ValueError("duration_minutes must be a positive PostgreSQL integer or null")
    return value


def _required_string(payload, field):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(payload, field):
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string or null")
    return value


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError("content_source_id must be a valid UUID")
    try:
        return UUID(value)
    except ValueError as error:
        raise ValueError("content_source_id must be a valid UUID") from error


def _http_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("url must be a non-empty HTTP or HTTPS URL")

    url = value.strip()
    if any(character.isspace() for character in url):
        raise ValueError("url must be a valid HTTP or HTTPS URL")

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("url must be a valid HTTP or HTTPS URL")
    return url


def _optional_timestamp(payload, field):
    value = payload.get(field)
    if value is None:
        return None
    return _timestamp(value, field)


def _timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a valid timestamp")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a valid timestamp") from error
    if timestamp.tzinfo is None:
        raise ValueError(f"{field} must be a valid timestamp")
    return timestamp
