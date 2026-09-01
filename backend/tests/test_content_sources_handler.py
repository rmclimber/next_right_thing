import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.content_sources import handler as content_sources_handler


def event(method, body=None, sub="cognito-user-sub", source_id="source-id"):
    result = {
        "requestContext": {
            "http": {
                "method": method,
            },
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": sub,
                    },
                },
            },
        },
        "pathParameters": {"id": source_id},
    }

    if body is not None:
        result["body"] = json.dumps(body)

    return result


def content_source_response(**overrides):
    response = {
        "id": "source-id",
        "name": "AWS Machine Learning Blog",
        "source_type": "rss",
        "url": "https://example.com/feed.xml",
        "status": "active",
        "created_at": "2026-09-01T12:00:00+00:00",
        "updated_at": "2026-09-01T12:00:00+00:00",
    }
    response.update(overrides)
    return response


class ContentSourcesHandlerTests(unittest.TestCase):
    def test_post_authenticated_successful_creation(self):
        repository = Mock()
        repository.create.return_value = content_source_response()

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(
                event(
                    "POST",
                    {
                        "name": " AWS Machine Learning Blog ",
                        "url": "https://example.com/feed.xml",
                    },
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 201)
        body = json.loads(response["body"])
        self.assertEqual(body["source_type"], "rss")
        self.assertEqual(body["status"], "active")
        user_id, new_source = repository.create.call_args.args
        self.assertEqual(user_id, "cognito-user-sub")
        self.assertEqual(new_source.name, "AWS Machine Learning Blog")
        self.assertEqual(new_source.url, "https://example.com/feed.xml")

    def test_post_uses_jwt_sub_for_user_id(self):
        repository = Mock()
        repository.create.return_value = content_source_response()

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            content_sources_handler.handler(
                event("POST", {"name": "Blog", "url": "https://example.com/feed.xml"}, sub="jwt-sub"),
                None,
            )

        self.assertEqual(repository.create.call_args.args[0], "jwt-sub")

    def test_post_rejects_blank_name(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(
                event("POST", {"name": "   ", "url": "https://example.com/feed.xml"}),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "name must be a non-empty string"})
        repository_class.assert_not_called()

    def test_post_rejects_invalid_url(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(event("POST", {"name": "Blog", "url": "ftp://example.com"}), None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "url must be a valid HTTP or HTTPS URL"})
        repository_class.assert_not_called()

    def test_post_rejects_malformed_json(self):
        request = event("POST")
        request["body"] = "{"

        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(request, None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "Request body must be valid JSON"})
        repository_class.assert_not_called()

    def test_post_rejects_request_supplied_system_fields(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(
                event(
                    "POST",
                    {
                        "name": "Blog",
                        "url": "https://example.com/feed.xml",
                        "user_id": "attacker-sub",
                        "source_type": "podcast",
                        "status": "paused",
                    },
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_post_duplicate_user_url_returns_409(self):
        repository = Mock()
        repository.create.side_effect = content_sources_handler.ContentSourceConflictError()

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(
                event("POST", {"name": "Blog", "url": "https://example.com/feed.xml"}),
                None,
            )

        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(json.loads(response["body"]), {"message": "Content source URL already exists"})

    def test_post_database_failure_returns_generic_server_error(self):
        repository = Mock()
        repository.create.side_effect = RuntimeError("database failed")

        with (
            patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository),
            patch.object(content_sources_handler.logger, "exception") as log_exception,
        ):
            response = content_sources_handler.handler(
                event("POST", {"name": "Blog", "url": "https://example.com/feed.xml"}),
                None,
            )

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Content source creation failed")

    def test_get_returns_authenticated_users_sources(self):
        repository = Mock()
        repository.list_for_user.return_value = [content_source_response()]

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("GET"), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["content_sources"][0]["id"], "source-id")
        repository.list_for_user.assert_called_once_with("cognito-user-sub")

    def test_get_empty_collection_succeeds(self):
        repository = Mock()
        repository.list_for_user.return_value = []

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("GET"), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"content_sources": []})

    def test_get_database_failure_returns_generic_server_error(self):
        repository = Mock()
        repository.list_for_user.side_effect = RuntimeError("database failed")

        with (
            patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository),
            patch.object(content_sources_handler.logger, "exception") as log_exception,
        ):
            response = content_sources_handler.handler(event("GET"), None)

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Content source listing failed")

    def test_patch_updates_name(self):
        repository = Mock()
        repository.update_for_user.return_value = content_source_response(name="AWS ML Blog")

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"name": " AWS ML Blog "}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["name"], "AWS ML Blog")
        source_id, user_id, source_update = repository.update_for_user.call_args.args
        self.assertEqual(source_id, "source-id")
        self.assertEqual(user_id, "cognito-user-sub")
        self.assertEqual(source_update.values, {"name": "AWS ML Blog"})

    def test_patch_updates_url(self):
        repository = Mock()
        repository.update_for_user.return_value = content_source_response(url="https://example.com/new.xml")

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"url": "https://example.com/new.xml"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(repository.update_for_user.call_args.args[2].values, {"url": "https://example.com/new.xml"})

    def test_patch_active_to_paused(self):
        repository = Mock()
        repository.update_for_user.return_value = content_source_response(status="paused")

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"status": "paused"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["status"], "paused")
        self.assertEqual(repository.update_for_user.call_args.args[2].values, {"status": "paused"})

    def test_patch_paused_to_active(self):
        repository = Mock()
        repository.update_for_user.return_value = content_source_response(status="active")

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"status": "active"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["status"], "active")

    def test_patch_archive(self):
        repository = Mock()
        repository.update_for_user.return_value = content_source_response(status="archived")

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"status": "archived"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["status"], "archived")

    def test_patch_returns_updated_at_from_successful_update(self):
        repository = Mock()
        repository.update_for_user.return_value = content_source_response(updated_at="2026-09-01T12:30:00+00:00")

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"name": "Updated"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["updated_at"], "2026-09-01T12:30:00+00:00")

    def test_patch_rejects_invalid_status(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(event("PATCH", {"status": "completed"}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_rejects_invalid_url(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(event("PATCH", {"url": "https://exa mple.com/feed.xml"}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_rejects_system_managed_fields(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(event("PATCH", {"updated_at": "2026-09-01T12:00:00+00:00"}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_rejects_empty_body(self):
        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(event("PATCH", {}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_rejects_malformed_json(self):
        request = event("PATCH")
        request["body"] = "{"

        with patch.object(content_sources_handler, "ContentSourceRepository") as repository_class:
            response = content_sources_handler.handler(request, None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "Request body must be valid JSON"})
        repository_class.assert_not_called()

    def test_patch_cross_user_or_inaccessible_source_returns_404(self):
        repository = Mock()
        repository.update_for_user.side_effect = content_sources_handler.ContentSourceNotFoundError()

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(
                event("PATCH", {"name": "Hijack"}, sub="user-b-sub", source_id="user-a-source"),
                None,
            )

        self.assertEqual(response["statusCode"], 404)
        source_id, user_id, _source_update = repository.update_for_user.call_args.args
        self.assertEqual(source_id, "user-a-source")
        self.assertEqual(user_id, "user-b-sub")

    def test_patch_duplicate_url_conflict_returns_409(self):
        repository = Mock()
        repository.update_for_user.side_effect = content_sources_handler.ContentSourceConflictError()

        with patch.object(content_sources_handler, "ContentSourceRepository", return_value=repository):
            response = content_sources_handler.handler(event("PATCH", {"url": "https://example.com/feed.xml"}), None)

        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(json.loads(response["body"]), {"message": "Content source URL already exists"})


if __name__ == "__main__":
    unittest.main()
