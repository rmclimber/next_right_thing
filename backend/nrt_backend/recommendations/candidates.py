from dataclasses import dataclass
from datetime import datetime
import re


ACTION_TYPE_READ_CONTENT_ITEM = "read_content_item"
DEFAULT_DURATION_MINUTES = 5
WORDS_PER_MINUTE = 225


@dataclass(frozen=True)
class CandidateAction:
    """An ephemeral action derived from a persisted Content Item."""

    action_type: str
    content_item_id: str
    title: str
    url: str
    summary: str | None
    estimated_duration_minutes: int
    published_at: datetime | None
    discovered_at: datetime
    created_at: datetime


def candidate_from_content_item(item: dict) -> CandidateAction:
    return CandidateAction(
        action_type=ACTION_TYPE_READ_CONTENT_ITEM,
        content_item_id=str(item["id"]),
        title=item["title"],
        url=item["url"],
        summary=item["summary"],
        estimated_duration_minutes=estimate_reading_duration(item["summary"]),
        published_at=item["published_at"],
        discovered_at=item["discovered_at"],
        created_at=item["created_at"],
    )


def estimate_reading_duration(summary: str | None) -> int:
    """Estimate summary reading time at 225 words/minute, defaulting to 5 minutes."""
    if not summary or not summary.strip():
        return DEFAULT_DURATION_MINUTES

    word_count = len(re.findall(r"\b[\w']+\b", summary))
    return max(1, (word_count + WORDS_PER_MINUTE - 1) // WORDS_PER_MINUTE)
