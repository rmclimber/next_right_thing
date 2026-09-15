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
    def __init__(self, fetchone_result=None):
        self.fetchone_result = fetchone_result
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        self.executions.append((query, params))

    def fetchone(self):
        return self.fetchone_result


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


if __name__ == "__main__":
    unittest.main()
