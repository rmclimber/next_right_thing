import logging
import os
from datetime import UTC, datetime

from nrt_backend.recommendations.candidates import candidate_from_content_item
from nrt_backend.recommendations.embedding_repository import EmbeddingRepository
from nrt_backend.recommendations.embeddings import semantic_relevances
from nrt_backend.recommendations.repository import RecommendationRepository
from nrt_backend.recommendations.scoring import ranked, score_candidate

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, repository=None, clock=None, *, ranking_mode=None, embedding_repository=None):
        self.repository = repository or RecommendationRepository()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.ranking_mode = ranking_mode if ranking_mode is not None else os.environ.get("RECOMMENDATION_RANKING_MODE", "baseline")
        if self.ranking_mode not in {"baseline", "shadow", "semantic"}:
            logger.warning("Unknown recommendation ranking mode; using baseline")
            self.ranking_mode = "baseline"
        self.embedding_repository = embedding_repository or EmbeddingRepository()

    def recommend_next(self, user_id: str, available_minutes: int) -> dict | None:
        goals = self.repository.list_active_goals(user_id)
        content_items = self.repository.list_recent_content_items(user_id)
        candidates = [candidate_from_content_item(item) for item in content_items]
        logger.info("loaded %d active goals", len(goals))
        logger.info("generated %d recommendation candidates", len(candidates))
        if not candidates:
            return None

        now = self.clock()
        recent_content_item_ids = set(self.repository.list_recent_recommended_content_item_ids(user_id))
        unsuppressed_candidates = [
            candidate for candidate in candidates
            if candidate.content_item_id not in recent_content_item_ids
        ]
        logger.info("recent recommendation suppression count=%d", len(recent_content_item_ids))
        if unsuppressed_candidates:
            selection_pool = unsuppressed_candidates
            logger.info("using diversity-filtered candidate pool")
        else:
            selection_pool = candidates
            logger.info("falling back to full eligible candidate pool")

        baseline = ranked([score_candidate(candidate, goals, available_minutes, now) for candidate in selection_pool])
        ordering = baseline
        semantic_used = False
        if self.ranking_mode != "baseline":
            semantic = self._semantic_ranking(user_id, selection_pool, content_items, goals, available_minutes, now)
            logger.info("recommendation ranking mode=%s semantic_ready=%s baseline_top=%s semantic_top=%s",
                        self.ranking_mode, semantic is not None,
                        [entry.candidate.content_item_id for entry in baseline[:3]],
                        [entry.candidate.content_item_id for entry in semantic[:3]] if semantic else [])
            if semantic is not None and self.ranking_mode == "semantic":
                ordering = semantic
                semantic_used = True
        winner = ordering[0]
        reason = _reason(winner, available_minutes, semantic_used=semantic_used)
        event_id = self.repository.create_event(user_id, winner.candidate, available_minutes, winner.total_score, reason)
        logger.info("selected recommendation content_item_id=%s", winner.candidate.content_item_id)
        logger.info("recommendation event persisted")
        return _response(event_id, winner.candidate, reason)

    def _semantic_ranking(self, user_id, selection_pool, content_items, goals, available_minutes, now):
        if not goals:
            logger.info("semantic fallback: no active Goals")
            return None
        try:
            ids = [candidate.content_item_id for candidate in selection_pool]
            embeddings = self.embedding_repository.load(user_id, ids, [str(goal["id"]) for goal in goals])
            selected_ids = set(ids)
            items = [item for item in content_items if str(item["id"]) in selected_ids]
            relevances = semantic_relevances(items, goals, embeddings)
            return ranked([score_candidate(candidate, goals, available_minutes, now,
                                           relevance=relevances[candidate.content_item_id])
                           for candidate in selection_pool])
        except Exception as error:  # noqa: BLE001 - optional ranking must never break baseline availability.
            logger.warning("semantic fallback: cache unavailable or incomplete error_type=%s", type(error).__name__)
            return None


def _reason(scored, available_minutes: int, *, semantic_used=False) -> str:
    recency_prefix = "Recent item" if scored.recency_score >= 0.7 else "Content item"
    if semantic_used:
        goal = f' using similarity to your goal "{scored.matching_goal_title}"' if scored.matching_goal_title else " using semantic ranking"
        return f"{recency_prefix} selected{goal}. Estimated duration: {scored.candidate.estimated_duration_minutes} minutes; available: {available_minutes} minutes."
    if scored.matching_goal_title:
        return f'{recency_prefix} that matches your goal "{scored.matching_goal_title}" and fits your {available_minutes}-minute window.'
    return f"{recency_prefix} that fits your {available_minutes}-minute window."


def _response(event_id: str, candidate, reason: str) -> dict:
    return {
        "recommendation_event_id": event_id,
        "action_type": candidate.action_type,
        "content_item": {
            "id": candidate.content_item_id,
            "content_type": candidate.content_type,
            "title": candidate.title,
            "url": candidate.url,
            "summary": candidate.summary,
            "published_at": candidate.published_at.isoformat() if candidate.published_at else None,
            "discovered_at": candidate.discovered_at.isoformat(),
            "content_source": candidate.content_source,
        },
        "estimated_duration_minutes": candidate.estimated_duration_minutes,
        "reason": reason,
    }
