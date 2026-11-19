import copy
import json
import unittest
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

from nrt_backend.recommendations.backfill import refresh
from nrt_backend.recommendations.embeddings import (
    DIMENSIONS,
    MODEL_ID,
    TitanEmbeddingProvider,
    embedding_text,
    semantic_relevances,
    text_hash,
    validated_vector,
)
from nrt_backend.recommendations.evaluate import evaluate
from nrt_backend.recommendations.service import RecommendationService

NOW = datetime(2026, 11, 18, 12, tzinfo=UTC)


def vector(x=1.0, y=0.0):
    return [x, y] + [0.0] * (DIMENSIONS - 2)


def item(item_id, title, direction):
    return {"id": item_id, "title": title, "summary": None, "embedding": direction,
            "url": "https://example.com/item", "content_type": "article", "duration_minutes": None,
            "published_at": NOW, "discovered_at": NOW, "created_at": NOW, "content_source": {}}


def subjects():
    return ([item("a", "Bayesian statistics course registration", vector(0, 1)),
             item("b", "Posterior inference with conjugate priors", vector())],
            [{"id": "g", "title": "Learn Bayesian statistics", "description": None, "embedding": vector()}])


def cache_for(items, goals):
    return {(kind, subject["id"]): {"text_hash": text_hash(embedding_text(subject, kind)),
                                    "vector": subject["embedding"]}
            for kind, collection in (("content_item", items), ("goal", goals)) for subject in collection}


class EmbeddingContractTests(unittest.TestCase):
    def test_representation_uses_only_relevant_text_and_normalizes_markup(self):
        content = {"title": "  Evidence &amp; practice ",
                   "summary": "<p>Clinical\n learning</p><script>tracking()</script><style>.ad{}</style>",
                   "url": "private-url", "duration_minutes": 10}
        self.assertEqual(embedding_text(content, "content_item"), "Evidence & practice Clinical learning")
        self.assertEqual(embedding_text({"title": "Goal", "description": None}, "goal"), "Goal")
        self.assertEqual(len(embedding_text({"title": "x" * 5000}, "content_item")), 4000)
        self.assertNotEqual(text_hash("one"), text_hash("two"))

    def test_provider_sends_versioned_model_dimensions_and_closes_response(self):
        client = Mock()
        body = BytesIO(json.dumps({"embedding": vector(2, 0)}).encode())
        client.invoke_model.return_value = {"body": body}
        self.assertEqual(TitanEmbeddingProvider(client).embed("Text"), vector())
        kwargs = client.invoke_model.call_args.kwargs
        self.assertEqual(kwargs["modelId"], MODEL_ID)
        self.assertEqual(json.loads(kwargs["body"]), {"inputText": "Text", "dimensions": 256, "normalize": True})
        self.assertTrue(body.closed)

    def test_provider_closes_malformed_response_and_propagates_failure_to_batch(self):
        client = Mock()
        body = BytesIO(b'{"embedding": [0]}')
        client.invoke_model.return_value = {"body": body}
        with self.assertRaises(ValueError):
            TitanEmbeddingProvider(client).embed("Text")
        self.assertTrue(body.closed)
        client.invoke_model.side_effect = RuntimeError("provider unavailable")
        with self.assertRaises(RuntimeError):
            TitanEmbeddingProvider(client).embed("Text")

    def test_invalid_vectors_are_rejected(self):
        for invalid in (None, [], [0.0] * DIMENSIONS, vector(float("nan")),
                        vector(float("inf")), vector(True), vector("1"), vector(10 ** 500), vector() + [0]):
            with self.subTest(invalid=str(invalid)[:30]), self.assertRaises(ValueError):
                validated_vector(invalid)

    def test_normalization_preserves_direction_for_extreme_finite_values(self):
        for magnitude in (5e-324, 1e308):
            with self.subTest(magnitude=magnitude):
                normalized = validated_vector(vector(magnitude, magnitude))
                self.assertAlmostEqual(normalized[0], 2 ** -0.5)
                self.assertAlmostEqual(sum(entry * entry for entry in normalized), 1.0)
        self.assertEqual(validated_vector([1e308] * DIMENSIONS), [1 / 16] * DIMENSIONS)

    def test_relevance_uses_best_goal_clamps_negative_and_is_deterministic(self):
        items, goals = subjects()
        goals.append({"id": "g2", "title": "Clinical practice", "description": "", "embedding": vector(0, 1)})
        items.append(item("c", "Unrelated", vector(-1, -1)))
        scores = semantic_relevances(items, goals, cache_for(items, goals))
        self.assertEqual(scores, {"a": (1.0, "Clinical practice"), "b": (1.0, "Learn Bayesian statistics"), "c": (0.0, None)})

    def test_empty_text_cannot_become_semantic_ready_even_with_a_matching_cache_hash(self):
        for kind in ("content_item", "goal"):
            with self.subTest(kind=kind):
                items, goals = subjects()
                subject = items[0] if kind == "content_item" else goals[0]
                subject["title"] = "<script>hidden</script>"
                with self.assertRaisesRegex(ValueError, "nonempty"):
                    semantic_relevances(items, goals, cache_for(items, goals))


class RefreshTests(unittest.TestCase):
    def test_refresh_skips_current_cache_and_regenerates_changed_or_invalid_vectors(self):
        current = {"id": "a", "title": "Current", "cached_hash": text_hash("Current"), "cached_vector": vector()}
        changed = {"id": "b", "title": "Changed", "cached_hash": text_hash("Old"), "cached_vector": vector()}
        invalid = {"id": "c", "title": "Invalid", "cached_hash": text_hash("Invalid"), "cached_vector": []}
        repository, provider = Mock(), Mock()
        repository.list_subjects.return_value = [current, changed, invalid]
        provider.embed.return_value = vector()
        result = refresh(repository, provider, "user", "content_item", limit=3)
        self.assertEqual(result, {"scanned": 3, "generated": 2, "skipped": 1, "failed": 0, "next_after_id": "c"})
        self.assertEqual([call.args[0] for call in provider.embed.call_args_list], ["Changed", "Invalid"])
        self.assertEqual(repository.save.call_count, 2)

    def test_failed_subject_leaves_cache_untouched_and_other_subjects_continue(self):
        repository, provider = Mock(), Mock()
        repository.list_subjects.return_value = [{"id": "a", "title": "Fail"}, {"id": "b", "title": "Pass"}]
        provider.embed.side_effect = [RuntimeError("outage"), vector()]
        result = refresh(repository, provider, "user", "goal", after_id="previous")
        self.assertEqual((result["generated"], result["failed"]), (1, 1))
        repository.save.assert_called_once_with("user", "goal", "b", text_hash("Pass"), vector())
        repository.list_subjects.assert_called_once_with("user", "goal", 100, "previous")

    def test_repeated_refresh_does_not_call_provider(self):
        repository, provider = Mock(), Mock()
        subject = {"id": "a", "title": "New", "description": "Goal"}
        repository.list_subjects.return_value = [subject]
        provider.embed.return_value = vector()
        refresh(repository, provider, "user", "goal")
        subject.update(cached_hash=text_hash("New Goal"), cached_vector=vector())
        refresh(repository, provider, "user", "goal")
        provider.embed.assert_called_once_with("New Goal")

    def test_invalid_provider_output_is_not_saved(self):
        repository, provider = Mock(), Mock()
        repository.list_subjects.return_value = [{"id": "a", "title": "Text"}]
        provider.embed.return_value = [float("nan")] * DIMENSIONS
        self.assertEqual(refresh(repository, provider, "user", "goal")["failed"], 1)
        repository.save.assert_not_called()


class SemanticServiceTests(unittest.TestCase):
    def setUp(self):
        self.items, self.goals = subjects()
        self.repository, self.embeddings = Mock(), Mock()
        self.repository.list_recent_content_items.return_value = self.items
        self.repository.list_active_goals.return_value = self.goals
        self.repository.list_recent_recommended_content_item_ids.return_value = []
        self.repository.create_event.return_value = "event"
        self.embeddings.load.return_value = cache_for(self.items, self.goals)

    def recommend(self, mode="semantic", minutes=20):
        return RecommendationService(self.repository, clock=lambda: NOW, ranking_mode=mode,
                                     embedding_repository=self.embeddings).recommend_next("user", minutes)

    def test_semantics_changes_winner_and_explanation_but_not_contract(self):
        result = self.recommend()
        self.assertEqual(result["content_item"]["id"], "b")
        self.assertIn('similarity to your goal "Learn Bayesian statistics"', result["reason"])
        self.assertEqual(result["action_type"], "consume_content_item")
        self.assertEqual(set(result), {"recommendation_event_id", "action_type", "content_item", "reason", "estimated_duration_minutes"})
        self.repository.create_event.assert_called_once()
        self.assertEqual(self.repository.create_event.call_args.args[4], result["reason"])

    def test_baseline_and_invalid_mode_never_read_embeddings(self):
        self.assertEqual(self.recommend("baseline")["content_item"]["id"], "a")
        self.assertEqual(self.recommend("typo")["content_item"]["id"], "a")
        self.embeddings.load.assert_not_called()

    def test_shadow_serves_and_persists_exact_baseline_while_logging_alternative(self):
        baseline = self.recommend("baseline")
        baseline_event = self.repository.create_event.call_args
        self.repository.create_event.reset_mock()
        with self.assertLogs("nrt_backend.recommendations.service", level="INFO") as logs:
            shadow = self.recommend("shadow")
        self.assertEqual(shadow, baseline)
        self.assertEqual(self.repository.create_event.call_args, baseline_event)
        self.repository.create_event.assert_called_once()
        self.assertIn("semantic_ready=True", " ".join(logs.output))
        self.assertIn("semantic_top=['b', 'a']", " ".join(logs.output))

    def test_missing_stale_or_invalid_embeddings_fall_back_for_whole_pool(self):
        original = cache_for(self.items, self.goals)
        for key in original:
            for fault in ("missing", "stale", "invalid"):
                with self.subTest(key=key, fault=fault):
                    cache = copy.deepcopy(original)
                    if fault == "missing":
                        del cache[key]
                    elif fault == "stale":
                        cache[key]["text_hash"] = "old"
                    else:
                        cache[key]["vector"] = vector(float("nan"))
                    self.embeddings.load.return_value = cache
                    self.assertEqual(self.recommend()["content_item"]["id"], "a")

    def test_changed_goal_or_content_invalidates_cached_text(self):
        self.goals[0]["description"] = "New focus"
        self.assertEqual(self.recommend()["content_item"]["id"], "a")
        self.goals[0]["description"] = None
        self.items[1]["summary"] = "Updated content"
        self.assertEqual(self.recommend()["content_item"]["id"], "a")

    def test_cache_read_failure_falls_back(self):
        self.embeddings.load.side_effect = RuntimeError("missing table or database unavailable")
        self.assertEqual(self.recommend()["content_item"]["id"], "a")

    def test_no_goals_and_no_content_need_no_embeddings(self):
        self.repository.list_active_goals.return_value = []
        self.assertEqual(self.recommend()["content_item"]["id"], "a")
        self.repository.list_recent_content_items.return_value = []
        self.assertIsNone(self.recommend())
        self.embeddings.load.assert_not_called()

    def test_recent_suppression_precedes_semantic_scoring_and_keeps_existing_fallback(self):
        self.repository.list_recent_recommended_content_item_ids.return_value = ["b"]
        self.assertEqual(self.recommend()["content_item"]["id"], "a")
        self.embeddings.load.assert_called_with("user", ["a"], ["g"])
        self.repository.list_recent_recommended_content_item_ids.return_value = ["a", "b"]
        self.assertEqual(self.recommend()["content_item"]["id"], "b")

    def test_over_window_item_can_win_and_known_or_unknown_duration_stays_intact(self):
        self.items[0]["title"] = "Unrelated"
        self.items[1]["duration_minutes"] = 40
        self.embeddings.load.return_value = cache_for(self.items, self.goals)
        result = self.recommend(minutes=5)
        self.assertEqual(result["content_item"]["id"], "b")
        self.assertEqual(result["estimated_duration_minutes"], 40)
        self.assertIn("available: 5 minutes", result["reason"])
        self.assertIsNone(self.items[0]["duration_minutes"])

    def test_semantic_ties_keep_deterministic_order(self):
        self.items[0]["embedding"] = vector()
        self.embeddings.load.return_value = cache_for(self.items, self.goals)
        self.assertEqual(self.recommend()["content_item"]["id"], "a")


class EvaluationTests(unittest.TestCase):
    def fixture(self):
        path = Path(__file__).resolve().parents[2] / "docs/features/semantic-relevance/evaluation-fixture.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_duplicate_item_ids_cannot_inflate_ranking_metrics(self):
        fixture = self.fixture()
        case = fixture["cases"][0]
        case["content_items"] = [case["content_items"][1], copy.deepcopy(case["content_items"][1])]
        case["labels"] = {"b": 2}
        with self.assertRaisesRegex(ValueError, "unique"):
            evaluate(fixture)

    def test_real_fixtures_cannot_bypass_validation_with_a_string_synthetic_flag(self):
        fixture = self.fixture()
        fixture["synthetic"] = "false"
        with self.assertRaisesRegex(ValueError, "boolean"):
            evaluate(fixture)

    def test_invalid_time_duration_and_goal_ids_are_rejected(self):
        for defect in ("timezone", "duration", "goal_ids"):
            with self.subTest(defect=defect):
                fixture = self.fixture()
                case = fixture["cases"][0]
                if defect == "timezone":
                    case["content_items"][0]["discovered_at"] = "2026-11-18T12:00:00"
                elif defect == "duration":
                    case["available_minutes"] = 0
                else:
                    case["goals"].append(copy.deepcopy(case["goals"][0]))
                with self.assertRaises(ValueError):
                    evaluate(fixture)

    def test_repeatable_fixture_results_include_fallback_and_improved_ordering(self):
        path = Path(__file__).resolve().parents[2] / "docs/features/semantic-relevance/evaluation-fixture.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        result = evaluate(fixture)
        self.assertEqual(result, evaluate(fixture))
        self.assertTrue(result["synthetic"])
        summary = result["summary"]
        self.assertEqual(summary["semantic_coverage"], 0.75)
        self.assertEqual(summary["changed_winners"], 3)
        self.assertGreater(summary["semantic_top1_relevance"], summary["baseline_top1_relevance"])
        self.assertGreater(summary["semantic_ndcg_at_3"], summary["baseline_ndcg_at_3"])

    def test_real_evaluation_rejects_unknown_model_and_missing_human_labels(self):
        path = Path(__file__).resolve().parents[2] / "docs/features/semantic-relevance/evaluation-fixture.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "model/representation key"):
            evaluate({**fixture, "synthetic": False, "model_key": "different-model"})
        fixture["cases"][0]["labels"]["a"] = None
        with self.assertRaisesRegex(ValueError, "relevance label"):
            evaluate(fixture)


if __name__ == "__main__":
    unittest.main()
