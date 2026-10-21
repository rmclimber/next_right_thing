import os
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.rss_fetch.source_health import (
    UPDATE_SOURCE_HEALTH_SQL,
    DataApiContentSourceHealthRepository,
)


class DataApiContentSourceHealthRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "DATABASE_CLUSTER_ARN": "cluster-arn",
                "DB_SECRET_ARN": "secret-arn",
                "DB_NAME": "nrt",
            },
            clear=True,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_updates_health_for_the_owned_source_only(self):
        client = Mock()
        client.execute_statement.return_value = {"numberOfRecordsUpdated": 1}

        updated = DataApiContentSourceHealthRepository(client).record(
            user_id="user-id",
            content_source_id="550e8400-e29b-41d4-a716-446655440000",
            status="healthy",
            error=None,
        )

        self.assertTrue(updated)
        call = client.execute_statement.call_args.kwargs
        self.assertEqual(call["resourceArn"], "cluster-arn")
        self.assertEqual(call["secretArn"], "secret-arn")
        self.assertEqual(call["database"], "nrt")
        self.assertEqual(call["sql"], UPDATE_SOURCE_HEALTH_SQL)
        self.assertIn("AND user_id = :user_id", UPDATE_SOURCE_HEALTH_SQL)
        self.assertIn("WHEN :status = 'healthy'", UPDATE_SOURCE_HEALTH_SQL)
        self.assertEqual(
            call["parameters"],
            [
                {"name": "status", "value": {"stringValue": "healthy"}},
                {"name": "content_source_id", "value": {"stringValue": "550e8400-e29b-41d4-a716-446655440000"}},
                {"name": "user_id", "value": {"stringValue": "user-id"}},
                {"name": "error", "value": {"isNull": True}},
            ],
        )

    def test_missing_owned_source_is_not_reported_as_an_update(self):
        client = Mock()
        client.execute_statement.return_value = {"numberOfRecordsUpdated": 0}

        updated = DataApiContentSourceHealthRepository(client).record(
            user_id="user-id",
            content_source_id="source-id",
            status="fetch_error",
            error="HTTP 404",
        )

        self.assertFalse(updated)

    def test_data_api_failure_surfaces_to_the_caller(self):
        client = Mock()
        client.execute_statement.side_effect = RuntimeError("RDS Data API unavailable")

        with self.assertRaisesRegex(RuntimeError, "RDS Data API unavailable"):
            DataApiContentSourceHealthRepository(client).record(
                user_id="user-id",
                content_source_id="source-id",
                status="fetch_error",
                error="HTTP 503",
            )
