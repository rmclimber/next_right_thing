from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from nrt_backend.shared.database import connect


CREATE_GOAL_SQL = """
INSERT INTO goals (
    id,
    user_id,
    title,
    description,
    status,
    target_date,
    created_at,
    updated_at,
    completed_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
)
RETURNING id, title, description, status, target_date, created_at, updated_at, completed_at;
"""


LIST_GOALS_SQL = """
SELECT id, title, description, status, target_date, created_at, updated_at, completed_at
FROM goals
WHERE user_id = %s
ORDER BY created_at DESC, id DESC;
"""


@dataclass(frozen=True)
class NewGoal:
    title: str
    description: str | None
    target_date: date | None


class GoalRepository:
    def create(self, user_id: str, new_goal: NewGoal):
        goal_id = uuid4()
        now = datetime.now(timezone.utc)
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    CREATE_GOAL_SQL,
                    (
                        goal_id,
                        user_id,
                        new_goal.title,
                        new_goal.description,
                        "active",
                        new_goal.target_date,
                        now,
                        now,
                        None,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()
            return _goal_from_row(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_for_user(self, user_id: str):
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(LIST_GOALS_SQL, (user_id,))
                rows = cursor.fetchall()
            return [_goal_from_row(row) for row in rows]
        finally:
            connection.close()


def _goal_from_row(row):
    (
        goal_id,
        title,
        description,
        status,
        target_date,
        created_at,
        updated_at,
        completed_at,
    ) = row

    return {
        "id": str(goal_id) if isinstance(goal_id, UUID) else goal_id,
        "title": title,
        "description": description,
        "status": status,
        "target_date": _date_value(target_date),
        "created_at": _datetime_value(created_at),
        "updated_at": _datetime_value(updated_at),
        "completed_at": _datetime_value(completed_at),
    }


def _date_value(value):
    if value is None:
        return None

    if isinstance(value, date):
        return value.isoformat()

    return value


def _datetime_value(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    return value
