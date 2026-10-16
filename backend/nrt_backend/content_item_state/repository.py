from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from nrt_backend.shared.database import connect


class ContentItemNotFoundError(ValueError):
    pass


class RecommendationEventValidationError(ValueError):
    pass


ACTION_DETAILS = {
    "snooze": ("active", "snoozed"),
    "complete": ("completed", "completed"),
    "archive": ("archived", "archived"),
}

OWNED_CONTENT_ITEM_SQL = "SELECT 1 FROM content_items WHERE id = %s AND user_id = %s;"
RECOMMENDATION_EVENT_SQL = "SELECT content_item_id FROM recommendation_events WHERE id = %s AND user_id = %s;"
UPSERT_STATE_SQL = """
INSERT INTO content_item_user_state (
    user_id, content_item_id, status, snoozed_until, completed_at, created_at, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (user_id, content_item_id) DO UPDATE SET
    status = EXCLUDED.status,
    snoozed_until = EXCLUDED.snoozed_until,
    completed_at = EXCLUDED.completed_at,
    updated_at = EXCLUDED.updated_at
RETURNING content_item_id, status, snoozed_until, completed_at;
"""
INSERT_EVENT_SQL = """
INSERT INTO user_action_events (
    id, user_id, content_item_id, recommendation_event_id, event_type, occurred_at
) VALUES (%s, %s, %s, %s, %s, %s);
"""


class ContentItemStateRepository:
    def apply_action(self, user_id: str, content_item_id: str, action: str, recommendation_event_id: str | None, now=None) -> dict:
        now = now or datetime.now(timezone.utc)
        item_id = UUID(content_item_id)
        recommendation_id = UUID(recommendation_event_id) if recommendation_event_id else None
        status, event_type = ACTION_DETAILS[action]
        snoozed_until = now + timedelta(hours=24) if action == "snooze" else None
        completed_at = now if action == "complete" else None
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(OWNED_CONTENT_ITEM_SQL, (item_id, user_id))
                if cursor.fetchone() is None:
                    raise ContentItemNotFoundError("Content Item not found")
                if recommendation_id:
                    cursor.execute(RECOMMENDATION_EVENT_SQL, (recommendation_id, user_id))
                    row = cursor.fetchone()
                    if row is None or row[0] != item_id:
                        raise RecommendationEventValidationError("recommendation_event_id is invalid for this Content Item")
                cursor.execute(UPSERT_STATE_SQL, (user_id, item_id, status, snoozed_until, completed_at, now, now))
                row = cursor.fetchone()
                cursor.execute(INSERT_EVENT_SQL, (uuid4(), user_id, item_id, recommendation_id, event_type, now))
            connection.commit()
            return _state_from_row(row)
        except (ContentItemNotFoundError, RecommendationEventValidationError):
            connection.rollback()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _state_from_row(row):
    content_item_id, status, snoozed_until, completed_at = row
    return {"content_item_id": str(content_item_id), "status": status,
            "snoozed_until": snoozed_until.isoformat() if snoozed_until else None,
            "completed_at": completed_at.isoformat() if completed_at else None}
