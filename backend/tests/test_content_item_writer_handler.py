import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.content_items.repository import ContentSourceOwnershipError
from nrt_backend.lambdas.content_item_writer import handler as writer_handler


def message(**overrides):
    body = {
        "user_id": "cognito-user-sub",
        "content_source_id": "550e8400-e29b-41d4-a716-446655440000",
        "external_id": "feed-guid",
        "title": "Example title",
        "url": "https://example.com/post",
        "summary": "Optional summary",
        "published_at": "2026-09-15T12:00:00Z",
        "discovered_at": "2026-09-15T13:00:00Z",
    }
    body.update(overrides)
    return {"messageId": "message-1", "body": json.dumps(body)}


class ContentItemWriterHandlerTests(unittest.TestCase):
    def test_valid_message_is_persisted(self):
        repository = Mock()
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message()]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        item = repository.create.call_args.args[0]
        self.assertEqual(item.user_id, "cognito-user-sub")
        self.assertEqual(str(item.content_source_id), "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(item.discovered_at.isoformat(), "2026-09-15T13:00:00+00:00")

    def test_malformed_json_is_acknowledged_without_persistence(self):
        repository = Mock()
        record = {"messageId": "bad-json", "body": "{"}
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [record]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        repository.create.assert_not_called()

    def test_missing_required_field_is_acknowledged(self):
        repository = Mock()
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message(title="")]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        repository.create.assert_not_called()

    def test_invalid_uuid_is_acknowledged(self):
        repository = Mock()
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message(content_source_id="not-a-uuid")]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        repository.create.assert_not_called()

    def test_invalid_url_is_acknowledged(self):
        repository = Mock()
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message(url="ftp://example.com")]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        repository.create.assert_not_called()

    def test_invalid_timestamp_is_acknowledged(self):
        repository = Mock()
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message(discovered_at="not-a-timestamp")]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        repository.create.assert_not_called()

    def test_system_managed_fields_are_acknowledged_without_persistence(self):
        repository = Mock()
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message(id="producer-id")]}, None)

        self.assertEqual(response, {"batchItemFailures": []})
        repository.create.assert_not_called()

    def test_ownership_mismatch_is_acknowledged(self):
        repository = Mock()
        repository.create.side_effect = ContentSourceOwnershipError("ownership mismatch")
        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message()]}, None)

        self.assertEqual(response, {"batchItemFailures": []})

    def test_transient_failure_retries_only_failed_record(self):
        repository = Mock()
        repository.create.side_effect = [None, RuntimeError("database unavailable")]
        second = message(external_id="second")
        second["messageId"] = "message-2"

        with patch.object(writer_handler, "ContentItemRepository", return_value=repository):
            response = writer_handler.handler({"Records": [message(), second]}, None)

        self.assertEqual(response, {"batchItemFailures": [{"itemIdentifier": "message-2"}]})
        self.assertEqual(repository.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
