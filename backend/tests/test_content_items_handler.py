import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.content_items import handler as content_items_handler


def event(method="GET", sub="cognito-user-sub"):
    return {
        "requestContext": {
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": {"sub": sub}}},
        }
    }


class ContentItemsHandlerTests(unittest.TestCase):
    def test_get_returns_only_authenticated_users_items(self):
        repository = Mock()
        repository.list_for_user.return_value = [{"id": "owned-item", "summary": None, "published_at": None}]

        with patch.object(content_items_handler, "ContentItemRepository", return_value=repository):
            response = content_items_handler.handler(event(sub="user-a-sub"), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"content_items": [{"id": "owned-item", "summary": None, "published_at": None}]})
        repository.list_for_user.assert_called_once_with("user-a-sub")

    def test_get_empty_collection_succeeds(self):
        repository = Mock()
        repository.list_for_user.return_value = []

        with patch.object(content_items_handler, "ContentItemRepository", return_value=repository):
            response = content_items_handler.handler(event(), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"content_items": []})

    def test_user_b_query_is_scoped_to_user_b(self):
        repository = Mock()
        repository.list_for_user.return_value = []

        with patch.object(content_items_handler, "ContentItemRepository", return_value=repository):
            content_items_handler.handler(event(sub="user-b-sub"), None)

        repository.list_for_user.assert_called_once_with("user-b-sub")

    def test_get_repository_failure_returns_generic_server_error(self):
        repository = Mock()
        repository.list_for_user.side_effect = RuntimeError("database password leaked")

        with (
            patch.object(content_items_handler, "ContentItemRepository", return_value=repository),
            patch.object(content_items_handler.logger, "exception") as log_exception,
        ):
            response = content_items_handler.handler(event(), None)

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Content Item listing failed")


if __name__ == "__main__":
    unittest.main()
