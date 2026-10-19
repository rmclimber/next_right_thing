import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from nrt_backend.content_items import repository
from nrt_backend.content_items.repository import (
    ContentItemRepository,
    ContentSourceOwnershipError,
    NewContentItem,
)


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
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def new_item():
    return NewContentItem(
        user_id="cognito-user-sub",
        content_source_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        external_id="feed-guid",
        title="Example title",
        url="https://example.com/post",
        summary=None,
        published_at=None,
        discovered_at=datetime(2026, 9, 15, 13, 0, tzinfo=timezone.utc),
    )


class ContentItemRepositoryTests(unittest.TestCase):
    def test_create_uses_atomic_parameterized_owned_source_insert(self):
        cursor = FakeCursor(fetchone_result=(True, True))
        connection = FakeConnection(cursor)
        item_id = UUID("11111111-1111-1111-1111-111111111111")

        with (
            patch.object(repository, "connect", return_value=connection),
            patch.object(repository, "uuid4", return_value=item_id),
        ):
            inserted = ContentItemRepository().create(new_item())

        query, params = cursor.executions[0]
        self.assertIn("WHERE id = %s", query)
        self.assertIn("AND user_id = %s", query)
        self.assertIn("INSERT INTO content_items", query)
        self.assertIn("ON CONFLICT (content_source_id, external_id) DO NOTHING", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(params[0:4], (new_item().content_source_id, "cognito-user-sub", item_id, "cognito-user-sub"))
        self.assertTrue(inserted)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_duplicate_is_successfully_idempotent(self):
        cursor = FakeCursor(fetchone_result=(True, False))
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            inserted = ContentItemRepository().create(new_item())

        self.assertFalse(inserted)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_unowned_source_does_not_create_content_item(self):
        cursor = FakeCursor(fetchone_result=(False, False))
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(ContentSourceOwnershipError):
                ContentItemRepository().create(new_item())

        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_list_returns_default_active_state_without_a_state_row(self):
        item_id = UUID("11111111-1111-1111-1111-111111111111")
        source_id = UUID("22222222-2222-2222-2222-222222222222")
        discovered_at = datetime(2026, 9, 15, 13, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchall_result=[
                (
                    item_id, source_id, "feed-guid", "Example title", "https://example.com/post",
                    None, None, discovered_at, discovered_at, discovered_at,
                    "active", None, None,
                )
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            result = ContentItemRepository().list_for_user("cognito-user-sub")

        query, params = cursor.executions[0]
        self.assertIn("LEFT JOIN content_item_user_state", query)
        self.assertIn("content_item_user_state.user_id = %s", query)
        self.assertIn("WHERE content_items.user_id = %s", query)
        self.assertIn("ORDER BY content_items.discovered_at DESC, content_items.created_at DESC, content_items.id DESC", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(params, ("cognito-user-sub", "cognito-user-sub"))
        self.assertEqual(result[0]["id"], str(item_id))
        self.assertEqual(result[0]["content_source_id"], str(source_id))
        self.assertIsNone(result[0]["summary"])
        self.assertIsNone(result[0]["published_at"])
        self.assertEqual(result[0]["discovered_at"], "2026-09-15T13:00:00+00:00")
        self.assertEqual(result[0]["status"], "active")
        self.assertIsNone(result[0]["snoozed_until"])
        self.assertIsNone(result[0]["completed_at"])
        self.assertTrue(connection.closed)

    def test_list_serializes_snoozed_completed_and_archived_state(self):
        item_id = UUID("11111111-1111-1111-1111-111111111111")
        source_id = UUID("22222222-2222-2222-2222-222222222222")
        timestamp = datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchall_result=[
                (item_id, source_id, "snoozed", "Snoozed", "https://example.com/snoozed", None, None, timestamp, timestamp, timestamp, "active", datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc), None),
                (item_id, source_id, "completed", "Completed", "https://example.com/completed", None, None, timestamp, timestamp, timestamp, "completed", None, timestamp),
                (item_id, source_id, "archived", "Archived", "https://example.com/archived", None, None, timestamp, timestamp, timestamp, "archived", None, None),
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            result = ContentItemRepository().list_for_user("user-a")

        self.assertEqual(result[0]["status"], "active")
        self.assertEqual(result[0]["snoozed_until"], "2026-10-20T13:00:00+00:00")
        self.assertEqual(result[1]["status"], "completed")
        self.assertEqual(result[1]["completed_at"], "2026-10-19T13:00:00+00:00")
        self.assertEqual(result[2]["status"], "archived")

    def test_list_join_uses_authenticated_user_state_only(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            ContentItemRepository().list_for_user("user-b")

        _, params = cursor.executions[0]
        self.assertEqual(params, ("user-b", "user-b"))


if __name__ == "__main__":
    unittest.main()
