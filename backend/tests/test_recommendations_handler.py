import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.recommendations import handler as recommendations_handler


def event(available_minutes="20", sub="user-a"):
    return {"requestContext": {"http": {"method": "GET"}, "authorizer": {"jwt": {"claims": {"sub": sub}}}},
            "queryStringParameters": {"available_minutes": available_minutes}}


class RecommendationHandlerTests(unittest.TestCase):
    def test_authenticated_success_uses_jwt_sub_only(self):
        service = Mock()
        service.recommend_next.return_value = {"recommendation_event_id": "event-a", "action_type": "read_content_item"}
        with patch.object(recommendations_handler, "RecommendationService", return_value=service):
            response = recommendations_handler.handler(event(), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["recommendation"]["recommendation_event_id"], "event-a")
        service.recommend_next.assert_called_once_with("user-a", 20)

    def test_no_candidates_is_successful_null_recommendation(self):
        service = Mock()
        service.recommend_next.return_value = None
        with patch.object(recommendations_handler, "RecommendationService", return_value=service):
            response = recommendations_handler.handler(event(), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"recommendation": None})

    def test_invalid_available_minutes_returns_400(self):
        for value in (None, "0", "241", "1.5", "-1"):
            response = recommendations_handler.handler(event(value), None)
            self.assertEqual(response["statusCode"], 400)

    def test_internal_error_is_generic(self):
        service = Mock()
        service.recommend_next.side_effect = RuntimeError("credentials")
        with patch.object(recommendations_handler, "RecommendationService", return_value=service):
            response = recommendations_handler.handler(event(), None)
        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})


if __name__ == "__main__":
    unittest.main()
