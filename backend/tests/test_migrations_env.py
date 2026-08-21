import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


def load_migration_env():
    env_path = Path(__file__).resolve().parents[1] / "migrations" / "env.py"
    spec = importlib.util.spec_from_file_location("nrt_test_migrations_env", env_path)
    module = importlib.util.module_from_spec(spec)

    import alembic.context as alembic_context
    import nrt_backend.shared.database as database
    import sqlalchemy

    config = Mock()
    config.config_file_name = None

    connection_context = Mock()
    connection_context.__enter__ = Mock(return_value=Mock())
    connection_context.__exit__ = Mock(return_value=False)

    connectable = Mock()
    connectable.connect.return_value = connection_context

    transaction_context = Mock()
    transaction_context.__enter__ = Mock(return_value=None)
    transaction_context.__exit__ = Mock(return_value=False)

    with (
        patch.object(alembic_context, "config", config, create=True),
        patch.object(alembic_context, "is_offline_mode", return_value=False),
        patch.object(alembic_context, "configure"),
        patch.object(alembic_context, "begin_transaction", return_value=transaction_context),
        patch.object(alembic_context, "run_migrations"),
        patch.object(
            database,
            "database_config",
            return_value={
                "host": "database.example.internal",
                "port": 5432,
                "dbname": "nrt",
                "secret_arn": "secret-arn",
            },
        ),
        patch.object(
            database,
            "database_credentials",
            return_value={
                "user": "db-user",
                "password": "db-password",
            },
        ),
        patch.object(sqlalchemy, "create_engine", return_value=connectable),
    ):
        spec.loader.exec_module(module)

    return module


class MigrationEnvTests(unittest.TestCase):
    def test_database_url_uses_database_configuration_and_secret_credentials(self):
        env = load_migration_env()

        with (
            patch.object(
                env,
                "database_config",
                return_value={
                    "host": "database.example.internal",
                    "port": 5432,
                    "dbname": "nrt",
                    "secret_arn": "secret-arn",
                },
            ),
            patch.object(
                env,
                "database_credentials",
                return_value={
                    "user": "db-user",
                    "password": "db-password",
                },
            ) as credentials,
        ):
            url = env._database_url()

        credentials.assert_called_once_with("secret-arn")
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.username, "db-user")
        self.assertEqual(url.password, "db-password")
        self.assertEqual(url.host, "database.example.internal")
        self.assertEqual(url.port, 5432)
        self.assertEqual(url.database, "nrt")


if __name__ == "__main__":
    unittest.main()
