import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from nrt_backend.content_item_state import repository
from nrt_backend.content_item_state.repository import ContentItemStateRepository


class Cursor:
    def __init__(self, rows): self.rows, self.executions = list(rows), []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params): self.executions.append((query, params))
    def fetchone(self): return self.rows.pop(0)


class Connection:
    def __init__(self, cursor): self.cursor_instance, self.committed, self.rolled_back = cursor, False, False
    def cursor(self): return self.cursor_instance
    def commit(self): self.committed = True
    def rollback(self): self.rolled_back = True
    def close(self): pass


class ContentItemStateRepositoryTests(unittest.TestCase):
    item_id = UUID("11111111-1111-1111-1111-111111111111")
    event_id = UUID("22222222-2222-2222-2222-222222222222")
    now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)

    def test_snooze_upserts_state_and_creates_linked_event_atomically(self):
        cursor = Cursor([(1,), (self.item_id,), (self.item_id, "active", datetime(2026, 10, 17, 12, tzinfo=timezone.utc), None)])
        connection = Connection(cursor)
        with patch.object(repository, "connect", return_value=connection):
            state = ContentItemStateRepository().apply_action("user-a", str(self.item_id), "snooze", str(self.event_id), self.now)
        self.assertEqual(state["status"], "active")
        self.assertEqual(state["snoozed_until"], "2026-10-17T12:00:00+00:00")
        self.assertEqual(len(cursor.executions), 4)
        self.assertIn("ON CONFLICT", cursor.executions[2][0])
        self.assertIn("INSERT INTO user_action_events", cursor.executions[3][0])
        self.assertEqual(cursor.executions[3][1][3], self.event_id)
        self.assertTrue(connection.committed)

    def test_complete_clears_snooze_and_sets_completion(self):
        cursor = Cursor([(1,), (self.item_id, "completed", None, self.now)])
        connection = Connection(cursor)
        with patch.object(repository, "connect", return_value=connection):
            state = ContentItemStateRepository().apply_action("user-a", str(self.item_id), "complete", None, self.now)
        self.assertEqual(state["status"], "completed")
        self.assertIsNone(state["snoozed_until"])
        self.assertEqual(state["completed_at"], self.now.isoformat())
        self.assertEqual(cursor.executions[2][1][4], "completed")

    def test_event_failure_rolls_back_state(self):
        class FailingCursor(Cursor):
            def execute(self, query, params):
                super().execute(query, params)
                if "INSERT INTO user_action_events" in query: raise RuntimeError("event failed")
        cursor = FailingCursor([(1,), (self.item_id, "archived", None, None)])
        connection = Connection(cursor)
        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(RuntimeError):
                ContentItemStateRepository().apply_action("user-a", str(self.item_id), "archive", None, self.now)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_state_failure_does_not_insert_event(self):
        class FailingCursor(Cursor):
            def execute(self, query, params):
                super().execute(query, params)
                if "content_item_user_state" in query: raise RuntimeError("state failed")
        cursor = FailingCursor([(1,)])
        connection = Connection(cursor)
        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(RuntimeError):
                ContentItemStateRepository().apply_action("user-a", str(self.item_id), "archive", None, self.now)
        self.assertTrue(connection.rolled_back)
        self.assertEqual(len(cursor.executions), 2)


if __name__ == "__main__": unittest.main()
