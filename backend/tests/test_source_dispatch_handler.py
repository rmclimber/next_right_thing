import json
import os
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.source_dispatch import handler as dispatch_handler


class SourceDispatchHandlerTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"FETCH_JOBS_QUEUE_URL": "https://sqs.example/jobs"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_active_rss_source_is_dispatched_with_the_fetch_job_contract(self):
        repository = Mock()
        repository.list_active_rss_sources.return_value = [
            {"id": "source-id", "user_id": "user-id", "url": "https://example.com/feed.xml"}
        ]
        sqs = Mock()
        with (
            patch.object(dispatch_handler, "ContentSourceRepository", return_value=repository),
            patch.object(dispatch_handler, "_sqs_client", return_value=sqs),
        ):
            dispatch_handler.handler({}, None)

        self.assertEqual(
            json.loads(sqs.send_message.call_args.kwargs["MessageBody"]),
            {"user_id": "user-id", "content_source_id": "source-id", "url": "https://example.com/feed.xml"},
        )

    def test_no_paused_archived_or_unsupported_sources_are_dispatched_when_query_returns_none(self):
        repository = Mock()
        repository.list_active_rss_sources.return_value = []
        sqs = Mock()
        with (
            patch.object(dispatch_handler, "ContentSourceRepository", return_value=repository),
            patch.object(dispatch_handler, "_sqs_client", return_value=sqs),
        ):
            dispatch_handler.handler({}, None)
        sqs.send_message.assert_not_called()

    def test_database_failure_surfaces(self):
        repository = Mock()
        repository.list_active_rss_sources.side_effect = RuntimeError("database unavailable")
        with patch.object(dispatch_handler, "ContentSourceRepository", return_value=repository):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                dispatch_handler.handler({}, None)

    def test_sqs_failure_surfaces(self):
        repository = Mock()
        repository.list_active_rss_sources.return_value = [{"id": "source-id", "user_id": "user-id", "url": "https://example.com/feed.xml"}]
        sqs = Mock()
        sqs.send_message.side_effect = RuntimeError("SQS unavailable")
        with (
            patch.object(dispatch_handler, "ContentSourceRepository", return_value=repository),
            patch.object(dispatch_handler, "_sqs_client", return_value=sqs),
            self.assertRaisesRegex(RuntimeError, "SQS unavailable"),
        ):
            dispatch_handler.handler({}, None)
