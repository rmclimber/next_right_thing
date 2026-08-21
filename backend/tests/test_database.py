import json
import os
import unittest
from unittest.mock import Mock, patch

from nrt_backend.shared import database


class DatabaseTests(unittest.TestCase):
    def test_connect_reads_secret_and_opens_postgresql_connection(self):
        secrets_client = Mock()
        secrets_client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {
                    "username": "db-user",
                    "password": "db-password",
                },
            ),
        }

        boto3 = Mock()
        boto3.client.return_value = secrets_client

        config_class = Mock()
        botocore_config = Mock()
        botocore_config.Config = config_class

        psycopg = Mock()
        connection = Mock()
        psycopg.connect.return_value = connection

        def import_module(name):
            return {
                "boto3": boto3,
                "botocore.config": botocore_config,
                "psycopg": psycopg,
            }[name]

        with (
            patch.dict(
                os.environ,
                {
                    "DB_HOST": "database.example.internal",
                    "DB_PORT": "5432",
                    "DB_NAME": "nrt",
                    "DB_SECRET_ARN": "secret-arn",
                },
                clear=True,
            ),
            patch.object(database, "import_module", side_effect=import_module),
        ):
            result = database.connect()

        self.assertIs(result, connection)
        config_class.assert_called_once_with(
            connect_timeout=2,
            read_timeout=2,
            retries={"max_attempts": 1},
        )
        boto3.client.assert_called_once_with(
            "secretsmanager",
            config=config_class.return_value,
        )
        secrets_client.get_secret_value.assert_called_once_with(SecretId="secret-arn")
        psycopg.connect.assert_called_once_with(
            host="database.example.internal",
            port=5432,
            dbname="nrt",
            user="db-user",
            password="db-password",
            connect_timeout=2,
        )


if __name__ == "__main__":
    unittest.main()
