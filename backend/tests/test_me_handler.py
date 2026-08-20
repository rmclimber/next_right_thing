import json
import unittest

from nrt_backend.lambdas.me.handler import handler


class MeHandlerTests(unittest.TestCase):
    def test_returns_authenticated_user_sub_from_jwt_claims(self):
        response = handler(
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
        self.assertEqual(json.loads(response["body"]), {"sub": "cognito-user-sub"})

    def test_missing_claims_preserves_existing_null_sub_behavior(self):
        response = handler({}, None)

        self.assertEqual(json.loads(response["body"]), {"sub": None})


if __name__ == "__main__":
    unittest.main()
