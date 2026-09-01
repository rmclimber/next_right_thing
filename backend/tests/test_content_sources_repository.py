import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from uuid import UUID

from nrt_backend.content_sources import repository
from nrt_backend.content_sources.repository import (
    ContentSourceConflictError,
    ContentSourceNotFoundError,
    ContentSourceRepository,
    ContentSourceUpdate,
    NewContentSource,
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


class UniqueViolation(Exception):
    sqlstate = "23505"


class ContentSourceRepositoryTests(unittest.TestCase):
    def test_create_query_uses_parameterized_sql(self):
        source_id = UUID("11111111-1111-1111-1111-111111111111")
        created_at = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_result=(
                source_id,
                "AWS Machine Learning Blog",
                "rss",
                "https://example.com/feed.xml",
                "active",
                created_at,
                created_at,
            ),
        )
        connection = FakeConnection(cursor)

        with (
            patch.object(repository, "connect", return_value=connection),
            patch.object(repository, "uuid4", return_value=source_id),
        ):
            result = ContentSourceRepository().create(
                "cognito-user-sub",
                NewContentSource(name="AWS Machine Learning Blog", url="https://example.com/feed.xml"),
            )

        query, params = cursor.executions[0]
        self.assertIn("INSERT INTO content_sources", query)
        self.assertIn("VALUES (\n    %s,", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(
            params[0:6],
            (
                source_id,
                "cognito-user-sub",
                "AWS Machine Learning Blog",
                "rss",
                "https://example.com/feed.xml",
                "active",
            ),
        )
        self.assertIsInstance(params[6], datetime)
        self.assertEqual(params[6].tzinfo, timezone.utc)
        self.assertIs(params[6], params[7])
        self.assertEqual(result["source_type"], "rss")
        self.assertEqual(result["status"], "active")
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_create_duplicate_url_raises_conflict(self):
        cursor = FakeCursor()
        cursor.execute = Mock(side_effect=UniqueViolation())
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(ContentSourceConflictError):
                ContentSourceRepository().create(
                    "cognito-user-sub",
                    NewContentSource(name="Blog", url="https://example.com/feed.xml"),
                )

        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_list_query_scopes_by_user_id(self):
        cursor = FakeCursor(fetchall_result=[])
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            result = ContentSourceRepository().list_for_user("cognito-user-sub")

        query, params = cursor.executions[0]
        self.assertIn("WHERE user_id = %s", query)
        self.assertIn("ORDER BY created_at DESC, id DESC", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(params, ("cognito-user-sub",))
        self.assertEqual(result, [])
        self.assertTrue(connection.closed)

    def test_update_query_scopes_by_source_id_and_user_id(self):
        updated_at = datetime(2026, 9, 1, 12, 30, tzinfo=timezone.utc)
        cursor = FakeCursor(
            fetchone_result=(
                "source-id",
                "AWS ML Blog",
                "rss",
                "https://example.com/feed.xml",
                "paused",
                datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
                updated_at,
            ),
        )
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            result = ContentSourceRepository().update_for_user(
                "source-id",
                "cognito-user-sub",
                ContentSourceUpdate(values={"name": "AWS ML Blog", "status": "paused"}),
            )

        query, params = cursor.executions[0]
        self.assertIn("UPDATE content_sources", query)
        self.assertIn("name = %s", query)
        self.assertIn("status = %s", query)
        self.assertIn("updated_at = %s", query)
        self.assertIn("WHERE id = %s", query)
        self.assertIn("AND user_id = %s", query)
        self.assertIn("RETURNING id, name, source_type, url, status, created_at, updated_at", query)
        self.assertNotIn("cognito-user-sub", query)
        self.assertEqual(params[0], "AWS ML Blog")
        self.assertEqual(params[1], "paused")
        self.assertIsInstance(params[2], datetime)
        self.assertEqual(params[2].tzinfo, timezone.utc)
        self.assertEqual(params[-2:], ("source-id", "cognito-user-sub"))
        self.assertEqual(result["status"], "paused")
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_update_returns_not_found_when_no_owned_source_matches(self):
        cursor = FakeCursor(fetchone_result=None)
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(ContentSourceNotFoundError):
                ContentSourceRepository().update_for_user(
                    "source-id",
                    "cognito-user-sub",
                    ContentSourceUpdate(values={"name": "AWS ML Blog"}),
                )

        query, params = cursor.executions[0]
        self.assertIn("WHERE id = %s", query)
        self.assertIn("AND user_id = %s", query)
        self.assertEqual(params[-2:], ("source-id", "cognito-user-sub"))
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_update_duplicate_url_raises_conflict(self):
        cursor = FakeCursor()
        cursor.execute = Mock(side_effect=UniqueViolation())
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(ContentSourceConflictError):
                ContentSourceRepository().update_for_user(
                    "source-id",
                    "cognito-user-sub",
                    ContentSourceUpdate(values={"url": "https://example.com/feed.xml"}),
                )

        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_update_rolls_back_database_failures(self):
        cursor = FakeCursor()
        cursor.execute = Mock(side_effect=RuntimeError("database failed"))
        connection = FakeConnection(cursor)

        with patch.object(repository, "connect", return_value=connection):
            with self.assertRaises(RuntimeError):
                ContentSourceRepository().update_for_user(
                    "source-id",
                    "cognito-user-sub",
                    ContentSourceUpdate(values={"name": "AWS ML Blog"}),
                )

        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
