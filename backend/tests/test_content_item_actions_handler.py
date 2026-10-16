import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.content_item_state.repository import ContentItemNotFoundError, RecommendationEventValidationError
from nrt_backend.lambdas.content_items import handler as content_items_handler


def event(body, sub="user-a", item_id="11111111-1111-1111-1111-111111111111"):
    return {"body": json.dumps(body), "pathParameters": {"id": item_id},
            "requestContext": {"http": {"method": "POST"}, "authorizer": {"jwt": {"claims": {"sub": sub}}}}}


class ContentItemActionsHandlerTests(unittest.TestCase):
    def test_valid_action_uses_authenticated_user_and_returns_state(self):
        service = Mock()
        service.apply_action.return_value = {"content_item_id": "item", "status": "completed", "snoozed_until": None, "completed_at": "now"}
        with patch.object(content_items_handler, "ContentItemStateService", return_value=service):
            response = content_items_handler.handler(event({"action": "complete", "recommendation_event_id": "22222222-2222-2222-2222-222222222222"}), None)
        self.assertEqual(response["statusCode"], 200)
        service.apply_action.assert_called_once_with("user-a", "11111111-1111-1111-1111-111111111111", "complete", "22222222-2222-2222-2222-222222222222")

    def test_invalid_action_and_malformed_body_return_400(self):
        self.assertEqual(content_items_handler.handler(event({"action": "opened"}), None)["statusCode"], 400)
        malformed = event({"action": "snooze"}); malformed["body"] = "{"
        self.assertEqual(content_items_handler.handler(malformed, None)["statusCode"], 400)

    def test_unowned_item_returns_404(self):
        service = Mock(); service.apply_action.side_effect = ContentItemNotFoundError()
        with patch.object(content_items_handler, "ContentItemStateService", return_value=service):
            self.assertEqual(content_items_handler.handler(event({"action": "archive"}), None)["statusCode"], 404)

    def test_invalid_recommendation_event_returns_400(self):
        service = Mock(); service.apply_action.side_effect = RecommendationEventValidationError("invalid")
        with patch.object(content_items_handler, "ContentItemStateService", return_value=service):
            self.assertEqual(content_items_handler.handler(event({"action": "snooze"}), None)["statusCode"], 400)


if __name__ == "__main__": unittest.main()
