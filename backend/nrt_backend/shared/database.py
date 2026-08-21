import json
import os
from importlib import import_module


class DatabaseConfigurationError(RuntimeError):
    """Raised when required database configuration is missing or invalid."""


def _required_env(name):
    value = os.environ.get(name)

    if not value:
        raise DatabaseConfigurationError(f"Missing required environment variable: {name}")

    return value


def _database_config():
    return {
        "host": _required_env("DB_HOST"),
        "port": int(_required_env("DB_PORT")),
        "dbname": _required_env("DB_NAME"),
        "secret_arn": _required_env("DB_SECRET_ARN"),
    }


def _database_credentials(secret_arn):
    boto3 = import_module("boto3")
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])

    return {
        "user": secret["username"],
        "password": secret["password"],
    }


def connect():
    config = _database_config()
    credentials = _database_credentials(config["secret_arn"])
    psycopg = import_module("psycopg")

    return psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["dbname"],
        user=credentials["user"],
        password=credentials["password"],
    )
