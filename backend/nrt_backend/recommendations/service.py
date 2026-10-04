from datetime import datetime, timezone
import logging

from nrt_backend.recommendations.candidates import candidate_from_content_item
from nrt_backend.recommendations.repository import RecommendationRepository
from nrt_backend.recommendations.scoring import ranked, score_candidate


logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, repository=None, clock=None):
        self.repository = repository or RecommendationRepository()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def recommend_next(self, user_id: str, available_minutes: int) -> dict | None:
        goals = self.repository.list_active_goals(user_id)
        content_items = self.repository.list_recent_content_items(user_id)
        candidates = [candidate_from_content_item(item) for item in content_items]
        logger.info("loaded %d active goals", len(goals))
        logger.info("generated %d recommendation candidates", len(candidates))
        if not candidates:
            return None

        now = self.clock()
        winner = ranked([score_candidate(candidate, goals, available_minutes, now) for candidate in candidates])[0]
        reason = _reason(winner, available_minutes)
        event_id = self.repository.create_event(user_id, winner.candidate, available_minutes, winner.total_score, reason)
        logger.info("selected recommendation content_item_id=%s", winner.candidate.content_item_id)
        logger.info("recommendation event persisted")
        return _response(event_id, winner.candidate, reason)


def _reason(scored, available_minutes: int) -> str:
    recency_prefix = "Recent item" if scored.recency_score >= 0.7 else "Content item"
    if scored.matching_goal_title:
        return f'{recency_prefix} that matches your goal "{scored.matching_goal_title}" and fits your {available_minutes}-minute window.'
    return f"{recency_prefix} that fits your {available_minutes}-minute window."


def _response(event_id: str, candidate, reason: str) -> dict:
    return {
        "recommendation_event_id": event_id,
        "action_type": candidate.action_type,
        "content_item": {
            "id": candidate.content_item_id,
            "title": candidate.title,
            "url": candidate.url,
            "summary": candidate.summary,
            "published_at": candidate.published_at.isoformat() if candidate.published_at else None,
            "discovered_at": candidate.discovered_at.isoformat(),
        },
        "estimated_duration_minutes": candidate.estimated_duration_minutes,
        "reason": reason,
    }
