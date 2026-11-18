"""Podcast metadata from feedparser entries; no source or storage contract changes."""

import re
from urllib.parse import urlparse


def audio_enclosure_url(entry):
    """Use the first valid HTTP(S) enclosure explicitly identified as audio."""
    for enclosure in entry.get("enclosures", []) or []:
        if not isinstance(enclosure, dict):
            continue
        media_type = enclosure.get("type")
        if not isinstance(media_type, str) or not media_type.split(";", 1)[0].strip().lower().startswith("audio/"):
            continue
        url = enclosure.get("href")
        if not isinstance(url, str):
            continue
        url = url.strip()
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            # urllib validates numeric port syntax and range only on access.
            _ = parsed.port
        except ValueError:
            continue
        if parsed.scheme in {"http", "https"} and hostname and not any(char.isspace() for char in url):
            return url
    return None


def duration_minutes(entry):
    """Parse iTunes seconds, MM:SS, or HH:MM:SS; round up to stored minutes."""
    value = entry.get("itunes_duration")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?::[0-9]{1,2}){0,2}", value.strip()):
        return None
    try:
        parts = [int(part) for part in value.strip().split(":")]
    except ValueError:
        return None
    if any(part >= 60 for part in parts[1:]):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    minutes = (seconds + 59) // 60
    return minutes if 1 <= minutes <= 2_147_483_647 else None


def description(entry):
    for field in ("summary", "itunes_summary", "subtitle"):
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for content in entry.get("content", []) or []:
        if not isinstance(content, dict):
            continue
        value = content.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
