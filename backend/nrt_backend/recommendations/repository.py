from datetime import datetime, timezone
from uuid import uuid4

from nrt_backend.shared.database import connect


CANDIDATE_POOL_LIMIT = 50

LIST_RECENT_CONTENT_ITEMS_SQL = """
SELECT content_items.id, content_items.title, content_items.url, content_items.summary,
       content_items.published_at, content_items.discovered_at, content_items.created_at,
       content_sources.id, content_sources.name, content_sources.url
FROM content_items
JOIN content_sources
  ON content_sources.id = content_items.content_source_id
 AND content_sources.user_id = content_items.user_id
LEFT JOIN content_item_user_state
  ON content_item_user_state.content_item_id = content_items.id
 AND content_item_user_state.user_id = content_items.user_id
WHERE content_items.user_id = %s
  AND (content_item_user_state.content_item_id IS NULL OR (
       content_item_user_state.status = 'active'
       AND (content_item_user_state.snoozed_until IS NULL OR content_item_user_state.snoozed_until <= NOW())
  ))
ORDER BY content_items.discovered_at DESC, content_items.created_at DESC, content_items.id DESC
LIMIT %s;
"""

LIST_ACTIVE_GOALS_SQL = """
SELECT id, title, description
FROM goals
WHERE user_id = %s AND status = 'active'
ORDER BY created_at DESC, id DESC;
"""

INSERT_RECOMMENDATION_EVENT_SQL = """
INSERT INTO recommendation_events (
    id, user_id, action_type, content_item_id, available_minutes,
    estimated_duration_minutes, score, reason, recommended_at, outcome
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id;
"""


class RecommendationRepository:
    def list_recent_content_items(self, user_id: str) -> list[dict]:
        return self._fetch_all(LIST_RECENT_CONTENT_ITEMS_SQL, (user_id, CANDIDATE_POOL_LIMIT), _content_item_from_row)

    def list_active_goals(self, user_id: str) -> list[dict]:
        return self._fetch_all(LIST_ACTIVE_GOALS_SQL, (user_id,), _goal_from_row)

    def create_event(self, user_id: str, candidate, available_minutes: int, score: float, reason: str) -> str:
        event_id = uuid4()
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_RECOMMENDATION_EVENT_SQL,
                    (event_id, user_id, candidate.action_type, candidate.content_item_id,
                     available_minutes, candidate.estimated_duration_minutes, score,
                     reason, datetime.now(timezone.utc), None),
                )
                row = cursor.fetchone()
            connection.commit()
            return str(row[0])
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _fetch_all(self, query, params, mapper):
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
            return [mapper(row) for row in rows]
        finally:
            connection.close()


def _content_item_from_row(row):
    item_id, title, url, summary, published_at, discovered_at, created_at, source_id, source_name, source_url = row
    return {"id": str(item_id), "title": title, "url": url, "summary": summary,
            "published_at": published_at, "discovered_at": discovered_at, "created_at": created_at,
            "content_source": {"id": str(source_id), "name": source_name, "url": source_url}}


def _goal_from_row(row):
    goal_id, title, description = row
    return {"id": str(goal_id), "title": title, "description": description}
