import json
import unittest
from unittest.mock import Mock, patch

from nrt_backend.lambdas.goals import handler as goals_handler


def event(method, body=None, sub="cognito-user-sub", goal_id="goal-id"):
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
        "pathParameters": {"id": goal_id},
    }

    if body is not None:
        result["body"] = json.dumps(body)

    return result


def goal_response(**overrides):
    response = {
        "id": "goal-id",
        "title": "Learn Bayesian statistics",
        "description": "Work through a practical text",
        "status": "active",
        "target_date": "2027-03-31",
        "created_at": "2026-08-22T12:00:00+00:00",
        "updated_at": "2026-08-22T12:30:00+00:00",
        "completed_at": None,
    }
    response.update(overrides)
    return response


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

    def test_patch_updates_title(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(title="Learn probability")

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"title": " Learn probability "}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["title"], "Learn probability")
        goal_id, user_id, goal_update = repository.update_for_user.call_args.args
        self.assertEqual(goal_id, "goal-id")
        self.assertEqual(user_id, "cognito-user-sub")
        self.assertEqual(goal_update.values, {"title": "Learn probability"})

    def test_patch_updates_description(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(description="Finish the text")

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"description": "Finish the text"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(repository.update_for_user.call_args.args[2].values, {"description": "Finish the text"})

    def test_patch_clears_description_with_null(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(description=None)

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"description": None}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(repository.update_for_user.call_args.args[2].values, {"description": None})

    def test_patch_updates_target_date(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(target_date="2027-04-30")

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"target_date": "2027-04-30"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(repository.update_for_user.call_args.args[2].values["target_date"].isoformat(), "2027-04-30")

    def test_patch_clears_target_date_with_null(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(target_date=None)

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"target_date": None}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(repository.update_for_user.call_args.args[2].values, {"target_date": None})

    def test_patch_active_to_paused(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(status="paused")

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"status": "paused"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["status"], "paused")
        self.assertEqual(repository.update_for_user.call_args.args[2].values, {"status": "paused"})

    def test_patch_active_to_completed_sets_completed_at(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(
            status="completed",
            completed_at="2026-08-22T12:30:00+00:00",
        )

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"status": "completed"}), None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["completed_at"], "2026-08-22T12:30:00+00:00")

    def test_patch_completed_to_active_clears_completed_at(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(status="active", completed_at=None)

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"status": "active"}), None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["status"], "active")
        self.assertIsNone(body["completed_at"])

    def test_patch_completed_goal_without_status_preserves_completed_at(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(
            status="completed",
            title="Learn Bayesian statistics deeply",
            completed_at="2026-08-22T12:00:00+00:00",
        )

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(
                event("PATCH", {"title": "Learn Bayesian statistics deeply"}),
                None,
            )

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["completed_at"], "2026-08-22T12:00:00+00:00")

    def test_patch_returns_updated_at_from_successful_update(self):
        repository = Mock()
        repository.update_for_user.return_value = goal_response(updated_at="2026-08-22T12:31:00+00:00")

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"description": "Updated"}), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["updated_at"], "2026-08-22T12:31:00+00:00")

    def test_patch_blank_title_fails(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(event("PATCH", {"title": "   "}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_invalid_target_date_fails(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(event("PATCH", {"target_date": "03/31/2027"}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_invalid_status_fails(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(event("PATCH", {"status": "done"}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_empty_body_fails(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(event("PATCH", {}), None)

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_unsupported_or_system_fields_fail(self):
        with patch.object(goals_handler, "GoalRepository") as repository_class:
            response = goals_handler.handler(
                event("PATCH", {"updated_at": "2026-08-22T12:00:00+00:00"}),
                None,
            )

        self.assertEqual(response["statusCode"], 400)
        repository_class.assert_not_called()

    def test_patch_nonexistent_or_inaccessible_goal_returns_404(self):
        repository = Mock()
        repository.update_for_user.side_effect = goals_handler.GoalNotFoundError()

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(event("PATCH", {"title": "Learn probability"}), None)

        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(json.loads(response["body"]), {"message": "Not found"})
        repository.update_for_user.assert_called_once()

    def test_patch_user_b_cannot_update_user_a_goal(self):
        repository = Mock()
        repository.update_for_user.side_effect = goals_handler.GoalNotFoundError()

        with patch.object(goals_handler, "GoalRepository", return_value=repository):
            response = goals_handler.handler(
                event("PATCH", {"title": "Hijack goal"}, sub="user-b-sub", goal_id="user-a-goal"),
                None,
            )

        self.assertEqual(response["statusCode"], 404)
        goal_id, user_id, _goal_update = repository.update_for_user.call_args.args
        self.assertEqual(goal_id, "user-a-goal")
        self.assertEqual(user_id, "user-b-sub")

    def test_patch_repository_failure_returns_generic_server_error(self):
        repository = Mock()
        repository.update_for_user.side_effect = RuntimeError("database credentials leaked here")

        with (
            patch.object(goals_handler, "GoalRepository", return_value=repository),
            patch.object(goals_handler.logger, "exception") as log_exception,
        ):
            response = goals_handler.handler(event("PATCH", {"title": "Learn probability"}), None)

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(json.loads(response["body"]), {"message": "Internal server error"})
        log_exception.assert_called_once_with("Goal update failed")


if __name__ == "__main__":
    unittest.main()
