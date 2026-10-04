from dataclasses import dataclass
from datetime import datetime, timezone
import re

from nrt_backend.recommendations.candidates import CandidateAction


RECENCY_WEIGHT = 0.40
GOAL_RELEVANCE_WEIGHT = 0.35
DURATION_FIT_WEIGHT = 0.25

STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "your",
})


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: CandidateAction
    recency_score: float
    goal_relevance_score: float
    duration_fit_score: float
    total_score: float
    matching_goal_title: str | None


def score_candidate(candidate: CandidateAction, goals: list[dict], available_minutes: int, now: datetime) -> ScoredCandidate:
    recency = recency_score(candidate, now)
    relevance, matching_goal_title = goal_relevance_score(candidate, goals)
    duration = duration_fit_score(candidate.estimated_duration_minutes, available_minutes)
    total = (
        RECENCY_WEIGHT * recency
        + GOAL_RELEVANCE_WEIGHT * relevance
        + DURATION_FIT_WEIGHT * duration
    )
    return ScoredCandidate(candidate, recency, relevance, duration, total, matching_goal_title)


def recency_score(candidate: CandidateAction, now: datetime) -> float:
    reference_time = candidate.published_at or candidate.discovered_at
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - reference_time).total_seconds() / 86_400)
    if age_days < 1:
        return 1.0
    if age_days < 7:
        return 0.7
    if age_days < 30:
        return 0.4
    return 0.1


def goal_relevance_score(candidate: CandidateAction, goals: list[dict]) -> tuple[float, str | None]:
    content_tokens = _tokens(f"{candidate.title} {candidate.summary or ''}")
    if not content_tokens or not goals:
        return 0.0, None

    best_score = 0.0
    best_title = None
    for goal in goals:
        goal_tokens = _tokens(f"{goal['title']} {goal.get('description') or ''}")
        if not goal_tokens:
            continue
        score = len(content_tokens.intersection(goal_tokens)) / len(goal_tokens)
        if score > best_score:
            best_score = score
            best_title = goal["title"]
    return best_score, best_title


def duration_fit_score(estimated_minutes: int, available_minutes: int) -> float:
    if estimated_minutes <= available_minutes:
        # A close fit is 1.0; a much shorter item remains useful at 0.5.
        return 0.5 + 0.5 * (estimated_minutes / available_minutes)
    if estimated_minutes <= available_minutes * 1.25:
        return 0.25
    return 0.0


def ranked(scored_candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    return sorted(
        scored_candidates,
        key=lambda scored: (
            -scored.total_score,
            -scored.candidate.discovered_at.timestamp(),
            -scored.candidate.created_at.timestamp(),
            scored.candidate.content_item_id,
        ),
    )


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS}
