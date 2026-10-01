import os
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.source_dispatch.repository import (
    LIST_ACTIVE_RSS_SOURCES_SQL,
    DataApiContentSourceRepository,
    _rds_data_client,
)


class DataApiContentSourceRepositoryTests(unittest.TestCase):
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

    def test_lists_active_rss_sources_with_the_existing_query_semantics(self):
        client = Mock()
        client.execute_statement.return_value = {
            "records": [
                [
                    {"stringValue": "source-id"},
                    {"stringValue": "user-id"},
                    {"stringValue": "https://example.com/feed.xml"},
                ]
            ]
        }

        sources = DataApiContentSourceRepository(client).list_active_rss_sources()

        self.assertEqual(
            sources,
            [{"id": "source-id", "user_id": "user-id", "url": "https://example.com/feed.xml"}],
        )
        client.execute_statement.assert_called_once_with(
            resourceArn="cluster-arn",
            secretArn="secret-arn",
            database="nrt",
            sql=LIST_ACTIVE_RSS_SOURCES_SQL,
        )
        self.assertIn("status = 'active'", LIST_ACTIVE_RSS_SOURCES_SQL)
        self.assertIn("source_type = 'rss'", LIST_ACTIVE_RSS_SOURCES_SQL)

    def test_zero_rows_returns_an_empty_source_list(self):
        client = Mock()
        client.execute_statement.return_value = {"records": []}

        self.assertEqual(DataApiContentSourceRepository(client).list_active_rss_sources(), [])

    def test_missing_records_returns_an_empty_source_list(self):
        client = Mock()
        client.execute_statement.return_value = {}

        self.assertEqual(DataApiContentSourceRepository(client).list_active_rss_sources(), [])

    def test_malformed_record_fails_visibly(self):
        client = Mock()
        client.execute_statement.return_value = {"records": [[{"stringValue": "source-id"}]]}

        with self.assertRaisesRegex(RuntimeError, "expected three source columns"):
            DataApiContentSourceRepository(client).list_active_rss_sources()

    def test_non_string_data_api_field_fails_visibly(self):
        client = Mock()
        client.execute_statement.return_value = {
            "records": [[{"stringValue": "source-id"}, {"isNull": True}, {"stringValue": "https://example.com/feed.xml"}]]
        }

        with self.assertRaisesRegex(RuntimeError, "user_id must be a stringValue"):
            DataApiContentSourceRepository(client).list_active_rss_sources()

    def test_data_api_failure_surfaces(self):
        client = Mock()
        client.execute_statement.side_effect = RuntimeError("RDS Data API unavailable")

        with self.assertRaisesRegex(RuntimeError, "RDS Data API unavailable"):
            DataApiContentSourceRepository(client).list_active_rss_sources()

    def test_creates_an_rds_data_boto3_client(self):
        boto3 = Mock()

        with patch("nrt_backend.lambdas.source_dispatch.repository.import_module", return_value=boto3):
            _rds_data_client()

        boto3.client.assert_called_once_with("rds-data")


if __name__ == "__main__":
    unittest.main()
