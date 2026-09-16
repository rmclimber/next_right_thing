import json
import os
import unittest
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from nrt_backend.lambdas.rss_fetch import handler as rss_handler


def record(body, message_id="message-1"):
    return {"messageId": message_id, "body": json.dumps(body) if isinstance(body, dict) else body}


JOB = {"user_id": "user-id", "content_source_id": "source-id", "url": "https://example.com/feed.xml"}


class RssFetchHandlerTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"NORMALIZED_CONTENT_ITEMS_QUEUE_URL": "https://sqs.example/normalized"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_rss_entry_normalizes_with_guid_and_publication_time(self):
        entries = [{"id": "rss-guid", "title": "Example", "link": "https://example.com/post", "summary": "Summary", "published_parsed": (2026, 9, 15, 12, 0, 0)}]
        sqs = Mock()
        with patch.object(rss_handler, "_feed_entries", return_value=entries), patch.object(rss_handler, "_sqs_client", return_value=sqs), patch.object(rss_handler, "_utc_now", return_value="2026-09-16T12:34:56Z"):
            response = rss_handler.handler({"Records": [record(JOB)]}, None)
        self.assertEqual(response, {"batchItemFailures": []})
        self.assertEqual(json.loads(sqs.send_message.call_args.kwargs["MessageBody"]), {"user_id": "user-id", "content_source_id": "source-id", "external_id": "rss-guid", "title": "Example", "url": "https://example.com/post", "summary": "Summary", "published_at": "2026-09-15T12:00:00Z", "discovered_at": "2026-09-16T12:34:56Z"})

    def test_atom_entry_uses_atom_id_and_allows_missing_summary_and_timestamp(self):
        entries = [{"id": "atom-id", "title": "Atom example", "link": "https://example.com/atom"}]
        sqs = Mock()
        with patch.object(rss_handler, "_feed_entries", return_value=entries), patch.object(rss_handler, "_sqs_client", return_value=sqs), patch.object(rss_handler, "_utc_now", return_value="2026-09-16T12:34:56Z"):
            rss_handler.handler({"Records": [record(JOB)]}, None)
        body = json.loads(sqs.send_message.call_args.kwargs["MessageBody"])
        self.assertEqual(body["external_id"], "atom-id")
        self.assertIsNone(body["summary"])
        self.assertIsNone(body["published_at"])

    def test_url_is_external_id_fallback_and_invalid_entries_are_skipped(self):
        entries = [
            {"title": "Fallback", "link": "https://example.com/fallback"},
            {"title": "No identity"},
            {"id": "no-title", "link": "https://example.com/no-title"},
        ]
        sqs = Mock()
        with patch.object(rss_handler, "_feed_entries", return_value=entries), patch.object(rss_handler, "_sqs_client", return_value=sqs), patch.object(rss_handler, "_utc_now", return_value="2026-09-16T12:34:56Z"):
            rss_handler.handler({"Records": [record(JOB)]}, None)
        self.assertEqual(json.loads(sqs.send_message.call_args.kwargs["MessageBody"])["external_id"], "https://example.com/fallback")
        self.assertEqual(sqs.send_message.call_count, 1)

    def test_malformed_job_is_acknowledged(self):
        response = rss_handler.handler({"Records": [record("{")]}, None)
        self.assertEqual(response, {"batchItemFailures": []})

    def test_timeout_and_retryable_http_status_are_retried(self):
        with patch.object(rss_handler, "_feed_entries", side_effect=rss_handler.RetryableFetchError("timeout")):
            response = rss_handler.handler({"Records": [record(JOB)]}, None)
        self.assertEqual(response, {"batchItemFailures": [{"itemIdentifier": "message-1"}]})

        with patch.object(rss_handler, "urlopen", side_effect=HTTPError(JOB["url"], 503, "service unavailable", {}, None)):
            with self.assertRaises(rss_handler.RetryableFetchError):
                rss_handler._feed_entries(JOB["url"])

    def test_permanent_http_4xx_is_acknowledged(self):
        with patch.object(rss_handler, "_feed_entries", side_effect=rss_handler.PermanentFeedError("HTTP 404")):
            response = rss_handler.handler({"Records": [record(JOB)]}, None)
        self.assertEqual(response, {"batchItemFailures": []})

    def test_only_failed_sqs_record_is_retried(self):
        sqs = Mock()
        sqs.send_message.side_effect = [None, RuntimeError("SQS unavailable")]
        entries = [{"id": "id", "title": "Entry", "link": "https://example.com/entry"}]
        second = dict(JOB, content_source_id="source-2")
        with patch.object(rss_handler, "_feed_entries", return_value=entries), patch.object(rss_handler, "_sqs_client", return_value=sqs):
            response = rss_handler.handler({"Records": [record(JOB), record(second, "message-2")]}, None)
        self.assertEqual(response, {"batchItemFailures": [{"itemIdentifier": "message-2"}]})
