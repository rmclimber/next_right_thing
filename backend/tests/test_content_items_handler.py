import base64
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from nrt_backend.lambdas.content_items import handler as api


def event(sub="user", query=None):
    return {"requestContext": {"http": {"method": "GET"},
            "authorizer": {"jwt": {"claims": {"sub": sub}}}}, "queryStringParameters": query}


class ContentItemsHandlerTests(unittest.TestCase):
    def test_defaults_preserve_fields_and_null_final_cursor(self):
        for items in ([], [{"id": "owned", "content_type": "podcast_episode", "duration_minutes": 42,
                             "summary": None, "published_at": None}]):
            repo = Mock()
            repo.list_for_user.return_value = (items, None)
            with patch.object(api, "ContentItemRepository", return_value=repo):
                response = api.handler(event(), None)
            self.assertEqual(response["statusCode"], 200)
            self.assertEqual(json.loads(response["body"]), {"content_items": items, "next_cursor": None})
            repo.list_for_user.assert_called_once_with("user", limit=50, filter="all", position=None)

    def test_valid_limits_filters_and_cursor_round_trip(self):
        position = (datetime(2026, 11, 20, 1, 2, 3, 123456, timezone.utc),
                    datetime(2026, 11, 20, tzinfo=timezone.utc), UUID(int=42))
        for limit in (1, 50, 100):
            for filter in ("all", "snoozed", "completed", "archived"):
                with self.subTest(limit=limit, filter=filter):
                    repo = Mock()
                    repo.list_for_user.return_value = ([{"id": "item"}], position)
                    token = api._encode_cursor(position, filter)
                    with patch.object(api, "ContentItemRepository", return_value=repo):
                        response = api.handler(event("user-b", {"limit": str(limit), "filter": filter, "cursor": token}), None)
                    self.assertEqual(response["statusCode"], 200)
                    self.assertEqual(json.loads(response["body"])["next_cursor"], token)
                    repo.list_for_user.assert_called_once_with("user-b", limit=limit, filter=filter, position=position)

    def test_invalid_queries_do_not_query_repository(self):
        payload = {"v": 1, "filter": "all", "discovered_at": "2026-11-20T00:00:00.123456+00:00",
                   "created_at": "2026-11-20T00:00:00Z", "id": str(UUID(int=42))}
        def token(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
        queries = [{"limit": value} for value in ("", "0", "101", "-1", "1.5", "1e2", " 50", "50 ", None, 50, "\uff11")]
        queries += [{"filter": value} for value in ("", "active", "All", None, [])]
        queries += [{"cursor": value} for value in ("", "!", "a", "x" * 2049, None, token([]), token({}))]
        for field, value in (("v", 2), ("v", True), ("filter", "completed"), ("id", "bad"),
                             ("discovered_at", "2026-11-20T00:00:00"), ("created_at", "2026-02-30T00:00:00Z"),
                             ("created_at", "2026-11-20T00:00:00.1234567Z"),
                             ("created_at", "2026-11-20T00:00:00+00:99"),
                             ("created_at", "0001-01-01T00:00:00+23:00"), ("id", 42)):
            queries.append({"cursor": token({**payload, field: value})})
        queries.append({"cursor": token({**payload, "user_id": "other-user"})})
        with patch.object(api, "ContentItemRepository") as repo:
            for query in queries:
                with self.subTest(query=query):
                    self.assertEqual(api.handler(event(query=query), None)["statusCode"], 400)
            repo.assert_not_called()

    def test_unauthenticated_listing_does_not_query_repository(self):
        with patch.object(api, "ContentItemRepository") as repo:
            self.assertEqual(api.handler(event(sub=None), None)["statusCode"], 401)
            repo.assert_not_called()

    def test_repository_failure_returns_generic_server_error(self):
        repo = Mock()
        repo.list_for_user.side_effect = RuntimeError("private database details")
        with patch.object(api, "ContentItemRepository", return_value=repo), patch.object(api.logger, "exception"):
            response = api.handler(event(), None)
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
