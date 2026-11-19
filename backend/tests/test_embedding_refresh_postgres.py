"""Execute the Data API adapter's real SQL in an isolated PostgreSQL schema.

Only the AWS HTTP transport is emulated. No AWS credentials or service calls.
"""

import json
import os
import re
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import psycopg
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from nrt_backend.lambdas.embedding_refresh.handler import run_refresh
from nrt_backend.recommendations import embedding_repository, repository
from nrt_backend.recommendations.data_api_embeddings import DataApiEmbeddingRepository
from nrt_backend.recommendations.embeddings import (
    DIMENSIONS,
    MODEL_KEY,
    embedding_text,
    text_hash,
)
from sqlalchemy import create_engine, text


class PostgresDataApiTransport:
    def __init__(self, connect):
        self.connect = connect
        self.calls = 0

    def execute_statement(self, *, resourceArn, secretArn, database, sql, parameters):
        self.calls += 1
        params = {}
        for parameter in parameters:
            value = parameter["value"]
            params[parameter["name"]] = None if value.get("isNull") else next(iter(value.values()))
        query = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
        with self.connect() as connection:
            cursor = connection.execute(query, params)
            rows = cursor.fetchall() if cursor.description else []
        records = []
        for row in rows:
            fields = []
            for value in row:
                if value is None:
                    fields.append({"isNull": True})
                elif type(value) is int:
                    fields.append({"longValue": value})
                else:
                    fields.append({"stringValue": value})
            if len(json.dumps(fields).encode()) > 64 * 1024:
                raise AssertionError("Data API row budget exceeded")
            records.append(fields)
        if len(json.dumps(records).encode()) > 1024 * 1024:
            raise AssertionError("Data API response budget exceeded")
        return {"records": records}


@unittest.skipUnless(os.environ.get("NRT_TEST_DATABASE_URL"), "NRT_TEST_DATABASE_URL is not set")
class EmbeddingRefreshPostgresTests(unittest.TestCase):
    def test_refresh_sql_parity_paging_long_text_ownership_and_invalidation(self):
        url = os.environ["NRT_TEST_DATABASE_URL"]
        schema = "refresh_" + uuid4().hex
        ids = {key: str(uuid4()) for key in ("source", "goal_a", "goal_b", "paused", "long", "short", "completed")}
        long_summary = "<script>" + "🧠" * 12000 + "</script><p>Bayesian inference and clinical learning</p>"
        engine = create_engine(url)
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        scripts = ScriptDirectory.from_config(config)
        try:
            with engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                with Operations.context(MigrationContext.configure(connection)):
                    for revision in reversed(list(scripts.walk_revisions())):
                        revision.module.upgrade()
                connection.execute(text("""
                    INSERT INTO content_sources (id, user_id, name, source_type, url, status, created_at, updated_at)
                    VALUES (:id, 'user-a', 'Feed', 'rss', 'https://example.com/feed', 'active', NOW(), NOW())
                """), {"id": ids["source"]})
                for key, user, status in (("goal_a", "user-a", "active"), ("goal_b", "user-b", "active"), ("paused", "user-a", "paused")):
                    connection.execute(text("""
                        INSERT INTO goals (id, user_id, title, description, status, created_at, updated_at)
                        VALUES (:id, :user, 'Professional learning', NULL, :status, NOW(), NOW())
                    """), {"id": ids[key], "user": user, "status": status})
                for key in ("long", "short", "completed"):
                    connection.execute(text("""
                        INSERT INTO content_items (id, user_id, content_source_id, external_id, title, summary,
                            url, content_type, duration_minutes, discovered_at, created_at, updated_at)
                        VALUES (:id, 'user-a', :source, :key, :title, :summary, 'https://example.com/item',
                            'article', NULL, NOW(), NOW(), NOW())
                    """), {"id": ids[key], "source": ids["source"], "key": key, "title": f"Item {key}",
                           "summary": long_summary if key == "long" else None})
                connection.execute(text("""
                    INSERT INTO content_item_user_state (user_id, content_item_id, status, created_at, updated_at)
                    VALUES ('user-a', :id, 'completed', NOW(), NOW())
                """), {"id": ids["completed"]})

            def connect(*, connect_timeout=30, statement_timeout_ms=0):
                return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"),
                                       connect_timeout=connect_timeout,
                                       options=f"-c search_path={schema} -c statement_timeout={statement_timeout_ms}")

            transport = PostgresDataApiTransport(connect)
            with patch.dict("os.environ", {"DATABASE_CLUSTER_ARN": "local", "DB_SECRET_ARN": "local", "DB_NAME": "local"}), \
                    patch.object(embedding_repository, "connect", side_effect=connect), \
                    patch.object(repository, "connect", side_effect=connect):
                data_api = DataApiEmbeddingRepository(transport)
                self.assertEqual(data_api.list_users(1), ["user-a"])
                self.assertEqual(data_api.list_users(1, "user-a"), ["user-b"])
                first = list(data_api.list_subjects("user-a", "content_item", 1))
                second = list(data_api.list_subjects("user-a", "content_item", 1, first[0]["id"]))
                self.assertNotEqual(first[0]["id"], second[0]["id"])
                subjects = list(data_api.list_subjects("user-a", "content_item", 10))
                long_item = next(subject for subject in subjects if subject["id"] == ids["long"])
                self.assertEqual(long_item["summary"], long_summary)
                self.assertEqual(embedding_text(long_item, "content_item"), "Item long Bayesian inference and clinical learning")

                provider = Mock()
                vector = [1.0] + [0.0] * (DIMENSIONS - 1)
                provider.embed.return_value = vector
                result = run_refresh(data_api, provider)
                self.assertEqual((result["generated"], result["users"]), (5, 2))
                self.assertEqual(provider.embed.call_count, 5)
                cache = embedding_repository.EmbeddingRepository().load("user-a", [ids["long"], ids["short"]], [ids["goal_a"]])
                self.assertEqual(cache[("content_item", ids["long"])]["text_hash"], text_hash(embedding_text(long_item, "content_item")))
                self.assertEqual(cache[("content_item", ids["long"])]["vector"], vector)
                repeated = run_refresh(data_api, provider)
                self.assertEqual((repeated["generated"], repeated["skipped"]), (0, 5))
                self.assertEqual(provider.embed.call_count, 5)
                with self.assertRaises(ValueError):
                    data_api.save("user-b", "content_item", ids["long"], "wrong-owner", vector)
                with connect() as connection:
                    connection.execute("UPDATE goals SET description = 'Updated interest' WHERE id = %s", (ids["goal_a"],))
                    connection.execute("UPDATE content_item_embeddings SET model_key = 'old-model' WHERE subject_id = %s", (ids["short"],))
                    connection.execute("UPDATE content_item_embeddings SET vector = %s::jsonb WHERE subject_id = %s",
                                       (json.dumps(["🧠" * 6] * DIMENSIONS), ids["long"]))
                repaired = run_refresh(data_api, provider)
                self.assertEqual((repaired["generated"], repaired["skipped"]), (3, 2))
                eligible = repository.RecommendationRepository().list_recent_content_items("user-a")
                self.assertEqual({row["id"] for row in eligible}, {ids["long"], ids["short"]})
                with connect() as connection:
                    self.assertEqual(connection.execute("SELECT count(*) FROM recommendation_events").fetchone()[0], 0)
                    self.assertEqual(connection.execute("SELECT count(*) FROM goal_embeddings WHERE model_key = %s", (MODEL_KEY,)).fetchone()[0], 2)
                    self.assertEqual(connection.execute("SELECT count(*) FROM goal_embeddings WHERE subject_id = %s", (ids["paused"],)).fetchone()[0], 0)
        finally:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
