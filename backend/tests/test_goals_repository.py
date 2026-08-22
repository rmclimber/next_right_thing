import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import UUID

from nrt_backend.goals import repository
from nrt_backend.goals.repository import GoalRepository, NewGoal


class FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        self.executions.append((query, params))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class GoalRepositoryTests(unittest.TestCase):
    def test_create_query_uses_parameterized_sql(self):
        goal_id = UUID("11111111-1111-1111-1111-111111111111")
        created_at = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_result=(
                goal_id,
                "Learn Bayesian statistics",
                "Work through a practical text",
                "active",
                date(2027, 3, 31),
                created_at,
                created_at,
                None,
            ),
        )
        connection = FakeConnection(cursor)

        with (
            patch.object(repository, "connect", return_value=connection),
            patch.object(repository, "uuid4", return_value=goal_id),
        ):
            result = GoalRepository().create(
                "cognito-user-sub",
                NewGoal(
                    title="Learn Bayesian statistics",
                    description="Work through a practical text",
                    target_date=date(2027, 3, 31),
                ),
            )

        query, params = cursor.executions[0]
        self.assertIn("VALUES (\n    %s,", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(params[0:6], (
            goal_id,
            "cognito-user-sub",
            "Learn Bayesian statistics",
            "Work through a practical text",
            "active",
            date(2027, 3, 31),
        ))
        self.assertIsInstance(params[6], datetime)
        self.assertEqual(params[6].tzinfo, timezone.utc)
        self.assertIs(params[6], params[7])
        self.assertIsNone(params[8])
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["target_date"], "2027-03-31")
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_list_query_scopes_by_user_id(self):
        cursor = FakeCursor(fetchall_result=[])
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            result = GoalRepository().list_for_user("cognito-user-sub")

        query, params = cursor.executions[0]
        self.assertIn("WHERE user_id = %s", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(params, ("cognito-user-sub",))
        self.assertEqual(result, [])
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
