import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from nrt_backend.recommendations.service import RecommendationService


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def content_item(item_id="item-a"):
    return {"id": item_id, "title": "Bayesian methods", "url": "https://example.com/article", "summary": "Bayesian statistics overview",
            "published_at": NOW, "discovered_at": NOW, "created_at": NOW}


class RecommendationServiceTests(unittest.TestCase):
    def test_winner_persists_one_event_for_authenticated_user(self):
        repository = Mock()
        repository.list_active_goals.return_value = [{"title": "Learn Bayesian statistics", "description": None}]
        repository.list_recent_content_items.return_value = [content_item()]
        repository.create_event.return_value = "event-id"

        result = RecommendationService(repository, clock=lambda: NOW).recommend_next("user-a", 20)

        self.assertEqual(result["recommendation_event_id"], "event-id")
        self.assertEqual(result["action_type"], "read_content_item")
        self.assertNotIn("user_id", result)
        self.assertIn("Learn Bayesian statistics", result["reason"])
        repository.create_event.assert_called_once()
        args = repository.create_event.call_args.args
        self.assertEqual(args[0], "user-a")
        self.assertEqual(args[1].content_item_id, "item-a")

    def test_no_candidates_does_not_create_event(self):
        repository = Mock()
        repository.list_active_goals.return_value = []
        repository.list_recent_content_items.return_value = []

        self.assertIsNone(RecommendationService(repository, clock=lambda: NOW).recommend_next("user-a", 20))
        repository.create_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
