import unittest
from unittest.mock import MagicMock, patch

from nrt_backend.recommendations import embedding_repository
from nrt_backend.shared import database


class EmbeddingCacheTimeoutTests(unittest.TestCase):
    def test_optional_cache_reads_use_short_connection_and_statement_timeouts(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchall.return_value = []
        with patch.object(embedding_repository, "connect", return_value=connection) as connect:
            embedding_repository.EmbeddingRepository().load("user", ["item"], [])
        connect.assert_called_once_with(connect_timeout=3, statement_timeout_ms=1000)
        connection.close.assert_called_once()

    def test_database_helper_passes_only_explicit_timeout_overrides(self):
        psycopg = MagicMock()
        with patch.object(database, "database_config", return_value={"host": "db", "port": 5432, "dbname": "nrt", "secret_arn": "secret"}), \
                patch.object(database, "database_credentials", return_value={"user": "user", "password": "pw"}), \
                patch.object(database, "import_module", return_value=psycopg):
            database.connect(connect_timeout=3, statement_timeout_ms=1000)
        self.assertEqual(psycopg.connect.call_args.kwargs["connect_timeout"], 3)
        self.assertEqual(psycopg.connect.call_args.kwargs["options"], "-c statement_timeout=1000")


if __name__ == "__main__":
    unittest.main()
