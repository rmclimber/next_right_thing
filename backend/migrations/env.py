import logging
import time
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import InterfaceError, OperationalError

from nrt_backend.shared.database import database_config, database_credentials


config = context.config
logger = logging.getLogger(__name__)

MAX_CONNECTION_ATTEMPTS = 3
CONNECTION_RETRY_DELAY_SECONDS = 5
CONNECTION_EXCEPTIONS = (OperationalError, InterfaceError)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url():
    db_config = database_config()
    credentials = database_credentials(db_config["secret_arn"])

    return URL.create(
        "postgresql+psycopg",
        username=credentials["user"],
        password=credentials["password"],
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["dbname"],
    )


def run_migrations_offline():
    raise RuntimeError("Offline migrations are not supported for NRT.")


def _connect_with_retry(connectable):
    for attempt in range(1, MAX_CONNECTION_ATTEMPTS + 1):
        try:
            return connectable.connect()
        except CONNECTION_EXCEPTIONS:
            if attempt == MAX_CONNECTION_ATTEMPTS:
                raise

            logger.warning(
                "Database connection attempt %s/%s failed; retrying in %s seconds",
                attempt,
                MAX_CONNECTION_ATTEMPTS,
                CONNECTION_RETRY_DELAY_SECONDS,
            )
            time.sleep(CONNECTION_RETRY_DELAY_SECONDS)


def run_migrations_online():
    connectable = create_engine(_database_url(), pool_pre_ping=True)

    with _connect_with_retry(connectable) as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
