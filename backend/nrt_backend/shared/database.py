import json
import logging
import os
from importlib import import_module


logger = logging.getLogger(__name__)


class DatabaseConfigurationError(RuntimeError):
    """Raised when required database configuration is missing or invalid."""


def _required_env(name):
    value = os.environ.get(name)

    if not value:
        raise DatabaseConfigurationError(f"Missing required environment variable: {name}")

    return value


def database_config():
    return {
        "host": _required_env("DB_HOST"),
        "port": int(_required_env("DB_PORT")),
        "dbname": _required_env("DB_NAME"),
        "secret_arn": _required_env("DB_SECRET_ARN"),
    }


def database_credentials(secret_arn):
    boto3 = import_module("boto3")
    botocore_config = import_module("botocore.config")
    logger.warning("Retrieving database credentials from Secrets Manager")
    client = boto3.client(
        "secretsmanager",
        config=botocore_config.Config(
            connect_timeout=2,
            read_timeout=2,
            retries={"max_attempts": 1},
        ),
    )
    response = client.get_secret_value(SecretId=secret_arn)
    logger.warning("Retrieved database credentials from Secrets Manager")
    secret = json.loads(response["SecretString"])

    return {
        "user": secret["username"],
        "password": secret["password"],
    }


_database_config = database_config
_database_credentials = database_credentials


def connect():
    config = database_config()
    credentials = database_credentials(config["secret_arn"])
    psycopg = import_module("psycopg")

    logger.warning("Opening PostgreSQL connection")
    return psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["dbname"],
        user=credentials["user"],
        password=credentials["password"],
        connect_timeout=30,
    )
