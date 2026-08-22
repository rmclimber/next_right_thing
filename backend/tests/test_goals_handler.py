import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.goals import handler as goals_handler


def event(method, body=None, sub="cognito-user-sub"):
    result = {
        "requestContext": {
            "http": {
                "method": method,
            },
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": sub,
                    },
                },
            },
        },
    }

    if body is not None:
        result["body"] = json.dumps(body)

    return result


class GoalsHandlerTests(unittest.TestCase):
    def test_post_authenticated_successful_creation(self):
        repository = Mock()
        repository.create.return_value = {
            "id": "goal-id",
            "title": "Learn Bayesian statistics",
            "description": "Work through a practical text",
            "status": "active",
            "target_date": "2027-03-31",
            "created_at": "2026-08-22T12:00:00+00:00",
            "updated_at": "2026-08-22T12:00:00+00:00",
            "completed_at": None,
        }

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(
                event(
                    "POST",
                    {
                        "title": " Learn Bayesian statistics ",
                        "description": "Work through a practical text",
                        "target_date": "2027-03-31",
                    },
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 201)
        self.assertEqual(json.loads(response["body"])["status"], "active")
        user_id, new_goal = repository.create.call_args.args
        self.assertEqual(user_id, "cognito-user-sub")
        self.assertEqual(new_goal.title, "Learn Bayesian statistics")
        self.assertEqual(new_goal.description, "Work through a practical text")
        self.assertEqual(new_goal.target_date.isoformat(), "2027-03-31")

    def test_post_rejects_request_supplied_system_fields(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(
                event(
                    "POST",
                    {
                        "title": "Learn Bayesian statistics",
                        "user_id": "attacker-sub",
                        "status": "completed",
                    },
                ),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_post_missing_or_blank_title_fails(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(event("POST", {"title": "   "}), None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "title must be a non-empty string"})
        repository_class.assert_not_called()

    def test_post_malformed_target_date_fails(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(
                event("POST", {"title": "Learn Bayesian statistics", "target_date": "03/31/2027"}),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "target_date must be a valid ISO date"})
        repository_class.assert_not_called()

    def test_post_rejects_iso_date_without_dashes(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(
                event("POST", {"title": "Learn Bayesian statistics", "target_date": "20270331"}),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(json.loads(response["body"]), {"message": "target_date must be a valid ISO date"})
        repository_class.assert_not_called()

    def test_post_repository_failure_returns_generic_server_error(self):
        repository = Mock()
        repository.create.side_effect = RuntimeError("database password nope")

        with (
            patch.object(goals_handler, "GoalRepository", return_value=repository),
            patch.object(goals_handler.logger, "exception") as log_exception,
        ):
            response = goals_handler.handler(
                event("POST", {"title": "Learn Bayesian statistics"}),
                None,
            )

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Goal creation failed")

    def test_get_returns_authenticated_users_goals(self):
        repository = Mock()
        repository.list_for_user.return_value = [
            {
                "id": "goal-id",
                "title": "Learn Bayesian statistics",
                "description": None,
                "status": "active",
                "target_date": None,
                "created_at": "2026-08-22T12:00:00+00:00",
                "updated_at": "2026-08-22T12:00:00+00:00",
                "completed_at": None,
            },
        ]

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("GET"), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["goals"][0]["id"], "goal-id")
        repository.list_for_user.assert_called_once_with("cognito-user-sub")

    def test_get_empty_list_succeeds(self):
        repository = Mock()
        repository.list_for_user.return_value = []

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("GET"), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"goals": []})

    def test_get_repository_failure_returns_generic_server_error(self):
        repository = Mock()
        repository.list_for_user.side_effect = RuntimeError("database failed")

        with (
            patch.object(goals_handler, "GoalRepository", return_value=repository),
            patch.object(goals_handler.logger, "exception") as log_exception,
        ):
            response = goals_handler.handler(event("GET"), None)

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Goal listing failed")


if __name__ == "__main__":
    unittest.main()
