import unittest
from datetime import datetime, timedelta, timezone

from nrt_backend.recommendations.candidates import candidate_from_content_item, estimate_reading_duration
from nrt_backend.recommendations.scoring import duration_fit_score, goal_relevance_score, ranked, recency_score, score_candidate


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def item(item_id="item-a", published_at=NOW, discovered_at=NOW, summary="Learn practical Bayesian statistics"):
    return {"id": item_id, "title": "Bayesian methods", "url": "https://example.com/article", "summary": summary,
            "content_type": "article", "duration_minutes": None,
            "published_at": published_at, "discovered_at": discovered_at, "created_at": discovered_at,
            "content_source": {"id": "source-a", "name": "Example feed", "url": "https://example.com/feed.xml"}}


class CandidateTests(unittest.TestCase):
    def test_content_item_becomes_consume_candidate_with_deterministic_duration(self):
        candidate = candidate_from_content_item(item(summary="word " * 1126))
        self.assertEqual(candidate.action_type, "consume_content_item")
        self.assertEqual(candidate.content_type, "article")
        self.assertEqual(candidate.estimated_duration_minutes, 6)

    def test_short_summary_uses_five_minute_minimum(self):
        self.assertEqual(estimate_reading_duration("Brief feed excerpt"), 5)

    def test_nullable_summary_and_published_at_are_supported(self):
        candidate = candidate_from_content_item(item(summary=None, published_at=None))
        self.assertEqual(candidate.estimated_duration_minutes, 5)
        self.assertIsNone(candidate.published_at)
        self.assertEqual(estimate_reading_duration(None), 5)

    def test_known_duration_overrides_estimate_without_minimum_or_time_window_cap(self):
        for duration in (1, 42, 600):
            with self.subTest(duration=duration):
                content = {**item(summary="word " * 1126), "content_type": "podcast_episode", "duration_minutes": duration}
                candidate = candidate_from_content_item(content)
                self.assertEqual(candidate.content_type, "podcast_episode")
                self.assertEqual(candidate.estimated_duration_minutes, duration)
                self.assertEqual(content["duration_minutes"], duration)

    def test_null_duration_keeps_estimate_ephemeral(self):
        content = item(summary="word " * 1126)
        self.assertEqual(candidate_from_content_item(content).estimated_duration_minutes, 6)
        self.assertIsNone(content["duration_minutes"])


class ScoringTests(unittest.TestCase):
    def test_type_does_not_affect_scoring_and_existing_article_score_is_unchanged(self):
        article = score_candidate(candidate_from_content_item(item()), [], 10, NOW)
        podcast = score_candidate(candidate_from_content_item({**item(), "content_type": "podcast_episode"}), [], 10, NOW)
        self.assertEqual(article.total_score, 0.40 + 0.25 * 0.75)
        self.assertEqual(article.total_score, podcast.total_score)

    def test_known_duration_flows_into_existing_duration_fit_score(self):
        candidate = candidate_from_content_item({**item(), "duration_minutes": 10})
        scored = score_candidate(candidate, [], 10, NOW)
        self.assertEqual(scored.duration_fit_score, 1.0)
        self.assertEqual(scored.total_score, 0.65)

    def test_newer_content_scores_higher_and_published_at_takes_precedence(self):
        newer = candidate_from_content_item(item(published_at=NOW - timedelta(hours=12)))
        older = candidate_from_content_item(item(published_at=NOW - timedelta(days=8)))
        self.assertGreater(recency_score(newer, NOW), recency_score(older, NOW))
        self.assertEqual(recency_score(candidate_from_content_item(item(published_at=NOW - timedelta(days=40), discovered_at=NOW)), NOW), 0.1)

    def test_discovered_at_is_recency_fallback(self):
        fresh = candidate_from_content_item(item(published_at=None, discovered_at=NOW))
        old = candidate_from_content_item(item(published_at=None, discovered_at=NOW - timedelta(days=31)))
        self.assertGreater(recency_score(fresh, NOW), recency_score(old, NOW))

    def test_goal_overlap_increases_relevance_and_inactive_goals_are_not_input(self):
        candidate = candidate_from_content_item(item())
        relevant, title = goal_relevance_score(candidate, [{"title": "Learn Bayesian statistics", "description": None}])
        unrelated, _ = goal_relevance_score(candidate, [{"title": "California licensing rules", "description": None}])
        self.assertGreater(relevant, unrelated)
        self.assertEqual(title, "Learn Bayesian statistics")
        self.assertEqual(goal_relevance_score(candidate, []), (0.0, None))

    def test_duration_fit_prefers_fit_and_close_fit(self):
        self.assertGreater(duration_fit_score(8, 10), duration_fit_score(20, 10))
        self.assertGreater(duration_fit_score(9, 10), duration_fit_score(2, 10))
        self.assertEqual(duration_fit_score(12, 10), 0.25)
        self.assertEqual(duration_fit_score(13, 10), 0.0)

    def test_ranking_uses_score_then_deterministic_content_item_id(self):
        first = score_candidate(candidate_from_content_item(item("item-b")), [], 10, NOW)
        second = score_candidate(candidate_from_content_item(item("item-a")), [], 10, NOW)
        self.assertEqual([entry.candidate.content_item_id for entry in ranked([first, second])], ["item-a", "item-b"])


if __name__ == "__main__":
    unittest.main()
