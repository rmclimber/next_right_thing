from datetime import datetime, timezone
from uuid import uuid4

from nrt_backend.shared.database import connect


CANDIDATE_POOL_LIMIT = 50

LIST_RECENT_CONTENT_ITEMS_SQL = """
SELECT id, title, url, summary, published_at, discovered_at, created_at
FROM content_items
WHERE user_id = %s
ORDER BY discovered_at DESC, created_at DESC, id DESC
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
    item_id, title, url, summary, published_at, discovered_at, created_at = row
    return {"id": str(item_id), "title": title, "url": url, "summary": summary,
            "published_at": published_at, "discovered_at": discovered_at, "created_at": created_at}


def _goal_from_row(row):
    goal_id, title, description = row
    return {"id": str(goal_id), "title": title, "description": description}
