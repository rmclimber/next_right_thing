from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from nrt_backend.shared.database import database_config, database_credentials


config = context.config

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


def run_migrations_online():
    connectable = create_engine(_database_url(), pool_pre_ping=True)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
