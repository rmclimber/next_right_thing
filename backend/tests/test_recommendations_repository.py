import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from nrt_backend.recommendations import repository
from nrt_backend.recommendations.candidates import candidate_from_content_item
from nrt_backend.recommendations.repository import RecommendationRepository


class FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.executions = []

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params): self.executions.append((query, params))
    def fetchone(self): return self.fetchone_result
    def fetchall(self): return self.fetchall_result


class FakeConnection:
    def __init__(self, cursor): self.cursor_instance, self.committed, self.closed = cursor, False, False
    def cursor(self): return self.cursor_instance
    def commit(self): self.committed = True
    def rollback(self): pass
    def close(self): self.closed = True


class RecommendationRepositoryTests(unittest.TestCase):
    def test_candidate_query_is_user_scoped_bounded_and_deterministically_ordered(self):
        cursor = FakeCursor()
        with patch.object(repository, "connect", return_value=FakeConnection(cursor)):
            RecommendationRepository().list_recent_content_items("user-a")
        query, params = cursor.executions[0]
        self.assertIn("WHERE user_id = %s", query)
        self.assertIn("ORDER BY discovered_at DESC, created_at DESC, id DESC", query)
        self.assertIn("LIMIT %s", query)
        self.assertEqual(params, ("user-a", 50))

    def test_goal_query_is_user_scoped_to_active_goals(self):
        cursor = FakeCursor()
        with patch.object(repository, "connect", return_value=FakeConnection(cursor)):
            RecommendationRepository().list_active_goals("user-a")
        query, params = cursor.executions[0]
        self.assertIn("user_id = %s AND status = 'active'", query)
        self.assertEqual(params, ("user-a",))

    def test_event_insert_is_parameterized_and_references_selected_content_item(self):
        event_id = UUID("11111111-1111-1111-1111-111111111111")
        cursor = FakeCursor(fetchone_result=(event_id,))
        connection = FakeConnection(cursor)
        candidate = candidate_from_content_item({
            "id": "22222222-2222-2222-2222-222222222222", "title": "Title", "url": "https://example.com",
            "summary": None, "published_at": None,
            "discovered_at": datetime(2026, 10, 4, tzinfo=timezone.utc), "created_at": datetime(2026, 10, 4, tzinfo=timezone.utc),
        })
        with patch.object(repository, "connect", return_value=connection):
            result = RecommendationRepository().create_event("user-a", candidate, 20, 0.8, "Reason")
        query, params = cursor.executions[0]
        self.assertIn("INSERT INTO recommendation_events", query)
        self.assertNotIn("user-a", query)
        self.assertEqual(params[1:6], ("user-a", "read_content_item", candidate.content_item_id, 20, 5))
        self.assertEqual(result, str(event_id))
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
