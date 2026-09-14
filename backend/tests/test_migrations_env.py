import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy.exc import OperationalError


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

    def test_connection_failure_is_retried_before_migrations_run(self):
        env = load_migration_env()
        connection = Mock()
        connection_context = Mock()
        connection_context.__enter__ = Mock(return_value=connection)
        connection_context.__exit__ = Mock(return_value=False)
        connectable = Mock()
        connectable.connect.side_effect = [
            OperationalError(None, None, Exception("database unavailable")),
            connection_context,
        ]

        transaction_context = Mock()
        transaction_context.__enter__ = Mock(return_value=None)
        transaction_context.__exit__ = Mock(return_value=False)

        with (
            patch.object(env, "create_engine", return_value=connectable),
            patch.object(env, "_database_url"),
            patch.object(env.context, "configure") as configure,
            patch.object(
                env.context,
                "begin_transaction",
                return_value=transaction_context,
            ),
            patch.object(env.context, "run_migrations") as run_migrations,
            patch.object(env.time, "sleep") as sleep,
            patch.object(env.logger, "warning") as warning,
        ):
            env.run_migrations_online()

        self.assertEqual(connectable.connect.call_count, 2)
        sleep.assert_called_once_with(5)
        warning.assert_called_once_with(
            "Database connection attempt %s/%s failed; retrying in %s seconds",
            1,
            3,
            5,
        )
        configure.assert_called_once_with(connection=connection, target_metadata=None)
        run_migrations.assert_called_once_with()

    def test_connection_failures_exhaust_retries(self):
        env = load_migration_env()
        failure = OperationalError(None, None, Exception("database unavailable"))
        connectable = Mock()
        connectable.connect.side_effect = failure

        with (
            patch.object(env.time, "sleep") as sleep,
            patch.object(env.logger, "warning") as warning,
        ):
            with self.assertRaisesRegex(OperationalError, "database unavailable"):
                env._connect_with_retry(connectable)

        self.assertEqual(connectable.connect.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(warning.call_count, 2)

    def test_migration_error_is_not_retried(self):
        env = load_migration_env()
        connection_context = Mock()
        connection_context.__enter__ = Mock(return_value=Mock())
        connection_context.__exit__ = Mock(return_value=False)
        connectable = Mock()
        connectable.connect.return_value = connection_context

        transaction_context = Mock()
        transaction_context.__enter__ = Mock(return_value=None)
        transaction_context.__exit__ = Mock(return_value=False)

        with (
            patch.object(env, "create_engine", return_value=connectable),
            patch.object(env, "_database_url"),
            patch.object(env.context, "configure"),
            patch.object(
                env.context,
                "begin_transaction",
                return_value=transaction_context,
            ),
            patch.object(
                env.context,
                "run_migrations",
                side_effect=RuntimeError("invalid migration"),
            ),
            patch.object(env.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid migration"):
                env.run_migrations_online()

        connectable.connect.assert_called_once_with()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
