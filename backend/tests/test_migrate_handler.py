import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from nrt_backend.lambdas.migrate import handler as migrate_handler


class MigrateHandlerTests(unittest.TestCase):
    def test_run_migrations_invokes_alembic_upgrade_to_head(self):
        config = Mock()
        script_directory = Mock()
        script_directory.get_current_head.return_value = "20260821_0001"

        with (
            patch.object(migrate_handler, "alembic_config", return_value=config),
            patch.object(migrate_handler.command, "upgrade") as upgrade,
            patch.object(
                migrate_handler.ScriptDirectory,
                "from_config",
                return_value=script_directory,
            ) as from_config,
        ):
            revision = migrate_handler.run_migrations()

        upgrade.assert_called_once_with(config, "head")
        from_config.assert_called_once_with(config)
        self.assertEqual(revision, "20260821_0001")

    def test_handler_returns_success_result_with_revision(self):
        with patch.object(
            migrate_handler,
            "run_migrations",
            return_value="20260821_0001",
        ):
            response = migrate_handler.handler({}, None)

        self.assertEqual(
            response,
            {
                "status": "ok",
                "revision": "20260821_0001",
            },
        )

    def test_handler_propagates_migration_failure(self):
        with (
            patch.object(
                migrate_handler,
                "run_migrations",
                side_effect=RuntimeError("migration failed"),
            ),
            patch.object(migrate_handler.logger, "exception") as log_exception,
        ):
            with self.assertRaises(RuntimeError):
                migrate_handler.handler({}, None)

        log_exception.assert_called_once_with("Database migration failed")

    def test_alembic_config_points_to_packaged_migration_files(self):
        config = migrate_handler.alembic_config()
        backend_root = Path(migrate_handler.__file__).resolve().parents[3]

        self.assertEqual(config.config_file_name, str(backend_root / "alembic.ini"))
        self.assertEqual(
            config.get_main_option("script_location"),
            str(backend_root / "migrations"),
        )


if __name__ == "__main__":
    unittest.main()
