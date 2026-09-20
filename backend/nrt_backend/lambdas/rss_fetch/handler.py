import json
import logging
import os
import socket
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from importlib import import_module
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
FETCH_TIMEOUT_SECONDS = 15
FETCH_JOB_FIELDS = {"user_id", "content_source_id", "url"}


class PermanentJobError(ValueError):
    pass


class PermanentFeedError(ValueError):
    pass


class RetryableFetchError(RuntimeError):
    pass


def handler(event, context):
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            job = _job_from_record(record)
            entries = _feed_entries(job["url"])
            discovered_at = _utc_now()
            items, skipped = _normalized_items(job, entries, discovered_at)
            _send_items(items)
            logger.info(
                "RSS feed processed: content_source_id=%s parsed=%s normalized=%s skipped=%s",
                job["content_source_id"], len(entries), len(items), skipped,
            )
        except (PermanentJobError, PermanentFeedError) as error:
            logger.warning("RSS fetch acknowledged: message_id=%s category=permanent error=%s", message_id, error)
        except Exception:
            logger.exception("RSS fetch failed: message_id=%s category=retryable", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}


def _job_from_record(record):
    try:
        payload = json.loads(record.get("body"))
    except (TypeError, json.JSONDecodeError) as error:
        raise PermanentJobError("body must be valid JSON") from error
    if not isinstance(payload, dict) or set(payload) != FETCH_JOB_FIELDS:
        raise PermanentJobError("body must contain only user_id, content_source_id, and url")
    return {
        "user_id": _required_string(payload, "user_id"),
        "content_source_id": _required_string(payload, "content_source_id"),
        "url": _http_url(payload.get("url")),
    }


def _feed_entries(url):
    request = Request(url, headers={"User-Agent": "NextRightThing/0.1 RSS Fetcher"})
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            body = response.read()
    except HTTPError as error:
        if error.code == 429 or error.code >= 500:
            raise RetryableFetchError(f"HTTP {error.code}") from error
        raise PermanentFeedError(f"HTTP {error.code}") from error
    except (URLError, socket.timeout, TimeoutError) as error:
        raise RetryableFetchError("network failure") from error

    parsed = import_module("feedparser").parse(body)
    if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
        raise PermanentFeedError("feed could not be parsed")
    return parsed.entries


def _normalized_items(job, entries, discovered_at):
    items = []
    skipped = 0
    for entry in entries:
        item = _normalize_entry(job, entry, discovered_at)
        if item is None:
            skipped += 1
        else:
            items.append(item)
    return items, skipped


def _normalize_entry(job, entry, discovered_at):
    external_id = _entry_string(entry, "id")
    url = _entry_string(entry, "link")
    if not external_id:
        external_id = url
    title = _entry_string(entry, "title")
    if not external_id or not title:
        return None
    try:
        url = _http_url(url)
    except PermanentJobError:
        return None
    return {
        "user_id": job["user_id"],
        "content_source_id": job["content_source_id"],
        "external_id": external_id,
        "title": title,
        "url": url,
        "summary": _entry_string(entry, "summary"),
        "published_at": _published_at(entry),
        "discovered_at": discovered_at,
    }


def _published_at(entry):
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    for field in ("published", "updated"):
        value = _entry_string(entry, field)
        if value:
            try:
                timestamp = parsedate_to_datetime(value)
                if timestamp.tzinfo is not None:
                    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError):
                pass
    return None


def _send_items(items):
    if not items:
        return
    queue_url = _required_env("NORMALIZED_CONTENT_ITEMS_QUEUE_URL")
    client = _sqs_client()
    for item in items:
        client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(item))


def _entry_string(entry, field):
    value = entry.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_string(payload, field):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PermanentJobError(f"{field} must be a non-empty string")
    return value.strip()


def _http_url(value):
    if not isinstance(value, str) or not value.strip() or any(char.isspace() for char in value):
        raise PermanentJobError("url must be a valid HTTP or HTTPS URL")
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PermanentJobError("url must be a valid HTTP or HTTPS URL")
    return url


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _sqs_client():
    return import_module("boto3").client("sqs")


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
