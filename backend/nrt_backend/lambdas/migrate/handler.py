import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


logger = logging.getLogger(__name__)


def alembic_config():
    backend_root = Path(__file__).resolve().parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return config


def run_migrations():
    config = alembic_config()
    logger.warning("Starting database migrations")
    command.upgrade(config, "head")
    revision = ScriptDirectory.from_config(config).get_current_head()
    logger.warning("Database migrations completed")
    return revision


def handler(event, context):
    try:
        revision = run_migrations()
    except Exception:
        logger.exception("Database migration failed")
        raise

    return {
        "status": "ok",
        "revision": revision,
    }
