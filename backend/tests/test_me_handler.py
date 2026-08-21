import json
import unittest
from unittest.mock import patch

from nrt_backend.lambdas.me import handler as me_handler


class FakeCursor:
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query):
        self.queries.append(query)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class MeHandlerTests(unittest.TestCase):
    def test_returns_authenticated_user_sub_from_jwt_claims(self):
        connection = FakeConnection()

        with patch.object(me_handler, "connect", return_value=connection):
            response = me_handler.handler(
                {
                    "requestContext": {
                        "authorizer": {
                            "jwt": {
                                "claims": {
                                    "sub": "cognito-user-sub",
                                },
                            },
                        },
                    },
                },
                None,
            )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"], {"content-type": "application/json"})
        self.assertEqual(
            json.loads(response["body"]),
            {
                "sub": "cognito-user-sub",
                "database": {
                    "connected": True,
                },
            },
        )
        self.assertEqual(connection.cursor_instance.queries, ["SELECT 1;"])
        self.assertTrue(connection.closed)

    def test_reports_database_connected_after_successful_smoke_query(self):
        connection = FakeConnection()

        with patch.object(me_handler, "connect", return_value=connection):
            response = me_handler.handler(
                {
                    "requestContext": {
                        "authorizer": {
                            "jwt": {
                                "claims": {
                                    "sub": "cognito-user-sub",
                                },
                            },
                        },
                    },
                },
                None,
            )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["database"], {"connected": True})
        self.assertEqual(connection.cursor_instance.queries, ["SELECT 1;"])
        self.assertTrue(connection.closed)

    def test_missing_claims_preserves_existing_null_sub_behavior(self):
        connection = FakeConnection()

        with patch.object(me_handler, "connect", return_value=connection):
            response = me_handler.handler({}, None)

        self.assertEqual(
            json.loads(response["body"]),
            {
                "sub": None,
                "database": {
                    "connected": True,
                },
            },
        )

    def test_returns_generic_500_when_database_connectivity_fails(self):
        with (
            patch.object(me_handler, "connect", side_effect=RuntimeError("boom")),
            patch.object(me_handler.logger, "exception") as log_exception,
        ):
            response = me_handler.handler(
                {
                    "requestContext": {
                        "authorizer": {
                            "jwt": {
                                "claims": {
                                    "sub": "cognito-user-sub",
                                },
                            },
                        },
                    },
                },
                None,
            )

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(response["headers"], {"content-type": "application/json"})
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Database connectivity smoke test failed")


if __name__ == "__main__":
    unittest.main()
