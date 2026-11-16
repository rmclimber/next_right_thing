from dataclasses import dataclass
from datetime import datetime
import re


ACTION_TYPE_CONSUME_CONTENT_ITEM = "consume_content_item"
DEFAULT_DURATION_MINUTES = 5
WORDS_PER_MINUTE = 225


@dataclass(frozen=True)
class CandidateAction:
    """An ephemeral action derived from a persisted Content Item."""

    action_type: str
    content_item_id: str
    content_type: str
    title: str
    url: str
    summary: str | None
    estimated_duration_minutes: int
    published_at: datetime | None
    discovered_at: datetime
    created_at: datetime
    content_source: dict


def candidate_from_content_item(item: dict) -> CandidateAction:
    return CandidateAction(
        action_type=ACTION_TYPE_CONSUME_CONTENT_ITEM,
        content_item_id=str(item["id"]),
        content_type=item["content_type"],
        title=item["title"],
        url=item["url"],
        summary=item["summary"],
        estimated_duration_minutes=resolve_duration_minutes(item["duration_minutes"], item["summary"]),
        published_at=item["published_at"],
        discovered_at=item["discovered_at"],
        created_at=item["created_at"],
        content_source=item["content_source"],
    )


def resolve_duration_minutes(duration_minutes: int | None, summary: str | None) -> int:
    """Prefer durable known duration; otherwise retain the deterministic estimate."""
    if duration_minutes is not None:
        return duration_minutes
    return estimate_reading_duration(summary)


def estimate_reading_duration(summary: str | None) -> int:
    """Estimate article reading time from its summary, with a five-minute minimum."""
    if not summary or not summary.strip():
        return DEFAULT_DURATION_MINUTES

    word_count = len(re.findall(r"\b[\w']+\b", summary))
    summary_estimate = (word_count + WORDS_PER_MINUTE - 1) // WORDS_PER_MINUTE
    return max(DEFAULT_DURATION_MINUTES, summary_estimate)
