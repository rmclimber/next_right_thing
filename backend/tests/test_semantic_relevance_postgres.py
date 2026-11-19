"""Real migration/cache/eligibility coverage, enabled with NRT_TEST_DATABASE_URL."""

import os
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import psycopg
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from nrt_backend.recommendations import embedding_repository, repository
from nrt_backend.recommendations.backfill import refresh
from nrt_backend.recommendations.embeddings import DIMENSIONS, MODEL_KEY
from nrt_backend.recommendations.service import RecommendationService
from sqlalchemy import create_engine, text


@unittest.skipUnless(os.environ.get("NRT_TEST_DATABASE_URL"), "NRT_TEST_DATABASE_URL is not set")
class SemanticPostgresTests(unittest.TestCase):
    def test_migration_refresh_recommend_eligibility_ownership_invalidation_and_downgrade(self):
        url = os.environ["NRT_TEST_DATABASE_URL"]
        schema = "semantic_" + uuid4().hex
        engine = create_engine(url)
        ids = {key: str(uuid4()) for key in (
            "source", "other_source", "goal", "paused_goal", "lexical", "semantic", "expired",
            "completed", "archived", "snoozed", "other_item",
        )}
        scripts_config = Config()
        scripts_config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        scripts = ScriptDirectory.from_config(scripts_config)
        try:
            with engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                with Operations.context(MigrationContext.configure(connection)):
                    for revision in reversed(list(scripts.walk_revisions())):
                        revision.module.upgrade()
                for source, user in (("source", "user"), ("other_source", "other")):
                    connection.execute(text("""
                        INSERT INTO content_sources (id, user_id, name, source_type, url, status, created_at, updated_at)
                        VALUES (:id, :user, 'Feed', 'rss', 'https://example.com/feed', 'active', NOW(), NOW())
                    """), {"id": ids[source], "user": user})
                for key, status in (("goal", "active"), ("paused_goal", "paused")):
                    connection.execute(text("""
                        INSERT INTO goals (id, user_id, title, status, created_at, updated_at)
                        VALUES (:id, 'user', 'Learn Bayesian statistics', :status, NOW(), NOW())
                    """), {"id": ids[key], "status": status})
                for key in ("lexical", "semantic", "expired", "completed", "archived", "snoozed", "other_item"):
                    title = {"lexical": "Learn Bayesian statistics registration",
                             "semantic": "Posterior inference with conjugate priors"}.get(key, "Unrelated")
                    connection.execute(text("""
                        INSERT INTO content_items (id, user_id, content_source_id, external_id, title, url,
                            duration_minutes, discovered_at, created_at, updated_at)
                        VALUES (:id, :user, :source, :key, :title, 'https://example.com/item', :duration, NOW(), NOW(), NOW())
                    """), {"id": ids[key], "user": "other" if key == "other_item" else "user",
                           "source": ids["other_source" if key == "other_item" else "source"], "key": key,
                           "title": title, "duration": 40 if key == "semantic" else None})
                for key in ("completed", "archived", "snoozed", "expired"):
                    connection.execute(text("""
                        INSERT INTO content_item_user_state (user_id, content_item_id, status, snoozed_until, created_at, updated_at)
                        VALUES ('user', :id, :status,
                            CASE WHEN :key = 'snoozed' THEN NOW() + INTERVAL '1 day'
                                 WHEN :key = 'expired' THEN NOW() - INTERVAL '1 day' ELSE NULL END,
                            NOW(), NOW())
                    """), {"id": ids[key], "key": key, "status": key if key in {"completed", "archived"} else "active"})

            def connect(*, connect_timeout=30, statement_timeout_ms=0):
                return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"),
                                       connect_timeout=connect_timeout,
                                       options=f"-c search_path={schema} -c statement_timeout={statement_timeout_ms}")

            cache = embedding_repository.EmbeddingRepository()
            recommendations = repository.RecommendationRepository()
            provider = Mock()
            provider.embed.side_effect = lambda value: (
                [1.0, 0.0] if value in {"Learn Bayesian statistics", "Posterior inference with conjugate priors"}
                else [0.0, 1.0]
            ) + [0.0] * (DIMENSIONS - 2)
            with patch.object(embedding_repository, "connect", side_effect=connect), patch.object(repository, "connect", side_effect=connect):
                eligible = recommendations.list_recent_content_items("user")
                self.assertEqual({row["id"] for row in eligible}, {ids[key] for key in ("lexical", "semantic", "expired")})
                self.assertEqual(len(recommendations.list_active_goals("user")), 1)
                self.assertEqual(refresh(cache, provider, "user", "content_item")["generated"], 6)
                self.assertEqual(refresh(cache, provider, "user", "goal")["generated"], 1)
                self.assertEqual(provider.embed.call_count, 7)
                self.assertEqual(refresh(cache, provider, "user", "content_item")["skipped"], 6)
                self.assertEqual(provider.embed.call_count, 7)
                page = cache.list_subjects("user", "content_item", 2)
                next_page = cache.list_subjects("user", "content_item", 2, page[-1]["id"])
                self.assertFalse({row["id"] for row in page} & {row["id"] for row in next_page})
                self.assertEqual(cache.load("other", [ids["semantic"]], [ids["goal"]]), {})
                with self.assertRaises(ValueError):
                    cache.save("other", "content_item", ids["semantic"], "wrong-owner", [0, 1] + [0] * (DIMENSIONS - 2))
                loaded = cache.load("user", [ids["semantic"]], [ids["goal"]])
                self.assertNotEqual(loaded[("content_item", ids["semantic"])]["text_hash"], "wrong-owner")

                service = RecommendationService(recommendations, ranking_mode="semantic", embedding_repository=cache,
                                                clock=lambda: datetime.now(UTC))
                # A cache-only lock must not prevent a baseline recommendation.
                # The lock session also has a guard timeout so a regression cannot
                # hang the test indefinitely.
                locker = connect()
                try:
                    locker.execute("SET idle_in_transaction_session_timeout = '4s'")
                    locker.execute("LOCK TABLE content_item_embeddings IN ACCESS EXCLUSIVE MODE")
                    fallback = service.recommend_next("user", 5)
                    self.assertEqual(fallback["content_item"]["id"], ids["lexical"])
                    self.assertNotIn("similarity", fallback["reason"])
                finally:
                    try:
                        locker.rollback()
                    except psycopg.OperationalError:
                        pass
                    locker.close()
                with connect() as connection:
                    connection.execute("DELETE FROM recommendation_events")
                selected = service.recommend_next("user", 5)
                self.assertEqual(selected["content_item"]["id"], ids["semantic"])
                self.assertEqual(selected["estimated_duration_minutes"], 40)
                self.assertEqual(provider.embed.call_count, 7)  # Inference never occurs in a recommendation.
                with connect() as connection:
                    connection.execute("DELETE FROM recommendation_events")
                    connection.execute("UPDATE goals SET description = 'Changed focus' WHERE id = %s", (ids["goal"],))
                fallback = service.recommend_next("user", 5)
                self.assertEqual(fallback["content_item"]["id"], ids["lexical"])
                self.assertNotIn("similarity", fallback["reason"])
                self.assertEqual(refresh(cache, provider, "user", "goal")["generated"], 1)
                with connect() as connection:
                    connection.execute("DELETE FROM recommendation_events")
                    connection.execute("UPDATE content_item_embeddings SET model_key = 'old-model' WHERE subject_id = %s", (ids["semantic"],))
                self.assertEqual(service.recommend_next("user", 5)["content_item"]["id"], ids["lexical"])
                self.assertEqual(refresh(cache, provider, "user", "content_item")["generated"], 1)
                with connect() as connection:
                    connection.execute("DELETE FROM goals WHERE id = %s", (ids["goal"],))
                    self.assertEqual(connection.execute("SELECT count(*) FROM goal_embeddings").fetchone()[0], 0)
                    self.assertEqual(connection.execute("SELECT count(*) FROM content_item_embeddings WHERE model_key = %s", (MODEL_KEY,)).fetchone()[0], 6)

            with engine.begin() as connection:
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                with Operations.context(MigrationContext.configure(connection)):
                    scripts.get_revision("20261118_0009").module.downgrade()
                self.assertEqual(connection.execute(text("SELECT count(*) FROM content_items")).scalar_one(), 7)
                self.assertEqual(connection.execute(text("SELECT count(*) FROM recommendation_events")).scalar_one(), 1)
        finally:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
