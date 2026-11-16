"""Contract migration checks; live PostgreSQL coverage uses NRT_TEST_DATABASE_URL."""

import importlib.util
from io import StringIO
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import psycopg
from sqlalchemy.exc import IntegrityError

from nrt_backend.content_items import repository as items_repository
from nrt_backend.lambdas.content_item_writer import handler as writer
from nrt_backend.lambdas.content_items import handler as items_api
from nrt_backend.lambdas.recommendations import handler as recommendations_api
from nrt_backend.recommendations import repository as recommendations_repository


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
SOURCE_ID = "550e8400-e29b-41d4-a716-446655440000"
ITEM_ID = "11111111-1111-1111-1111-111111111111"


def contract_migration():
    spec = importlib.util.spec_from_file_location(
        "content_contract_migration", MIGRATIONS / "versions" / "20261116_0008_generalize_content_items.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContentItemContractMigrationTests(unittest.TestCase):
    def test_postgresql_upgrade_ddl_backfills_and_constrains_without_rewriting_history(self):
        output = StringIO()
        context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
        with Operations.context(context):
            contract_migration().upgrade()
        sql = output.getvalue()
        self.assertIn("content_type TEXT DEFAULT 'article' NOT NULL", sql)
        self.assertIn("duration_minutes INTEGER", sql)
        self.assertIn("CHECK (duration_minutes > 0)", sql)
        self.assertIn("CHECK (content_type IN ('article', 'podcast_episode', 'video', 'research_article', 'book'))", sql)
        self.assertNotIn("recommendation_events", sql)

    def test_postgresql_downgrade_removes_only_new_contract(self):
        output = StringIO()
        context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
        with Operations.context(context):
            contract_migration().downgrade()
        sql = output.getvalue()
        self.assertIn("DROP COLUMN duration_minutes", sql)
        self.assertIn("DROP COLUMN content_type", sql)
        self.assertNotIn("recommendation_events", sql)


@unittest.skipUnless(os.environ.get("NRT_TEST_DATABASE_URL"), "NRT_TEST_DATABASE_URL is not set")
class ContentItemContractPostgresTests(unittest.TestCase):
    def test_migrate_legacy_data_then_ingest_list_recommend_and_downgrade(self):
        import json
        from sqlalchemy import create_engine, text

        url = os.environ["NRT_TEST_DATABASE_URL"]
        schema = "contract_" + uuid4().hex
        engine = create_engine(url)
        try:
            with engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                context = MigrationContext.configure(connection)
                config = Config()
                config.set_main_option("script_location", str(MIGRATIONS))
                scripts = ScriptDirectory.from_config(config)
                with Operations.context(context):
                    for revision in reversed(list(scripts.walk_revisions(base="base", head="20261020_0007"))):
                        revision.module.upgrade()
                connection.execute(text("""
                    INSERT INTO content_sources (id, user_id, name, source_type, url, status, created_at, updated_at)
                    VALUES (:source, 'contract-user', 'Feed', 'rss', 'https://example.com/feed', 'active', NOW(), NOW())
                """), {"source": SOURCE_ID})
                connection.execute(text("""
                    INSERT INTO content_items (id, user_id, content_source_id, external_id, title, url, discovered_at, created_at, updated_at)
                    VALUES (:item, 'contract-user', :source, 'legacy', 'Legacy article', 'https://example.com/legacy', NOW(), NOW(), NOW())
                """), {"item": ITEM_ID, "source": SOURCE_ID})
                connection.execute(text("""
                    INSERT INTO recommendation_events (id, user_id, action_type, content_item_id, available_minutes,
                        estimated_duration_minutes, score, reason, recommended_at)
                    VALUES (:event, 'contract-user', 'read_content_item', :item, 20, 5, 0.5, 'Legacy reason', NOW())
                """), {"event": str(uuid4()), "item": ITEM_ID})
                with Operations.context(context):
                    contract_migration().upgrade()
                self.assertEqual(connection.execute(text("SELECT content_type, duration_minutes FROM content_items")).one(), ("article", None))

            def connect():
                return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"), options=f"-c search_path={schema}")

            # Both old producers and the extended contract use the real Writer and repositories.
            with patch.object(items_repository, "connect", side_effect=connect):
                for content_type, duration in ((None, None), ("article", 1), ("podcast_episode", 42), ("video", 18), ("research_article", None), ("book", 600)):
                    payload = {"user_id": "contract-user", "content_source_id": SOURCE_ID,
                               "external_id": content_type or "old-producer", "title": "Contract item",
                               "url": "https://example.com/item", "discovered_at": "2026-11-16T12:00:00Z"}
                    if content_type is not None:
                        payload.update(content_type=content_type, duration_minutes=duration)
                    record = {"messageId": "contract", "body": json.dumps(payload)}
                    for _ in range(2):
                        self.assertEqual(writer.handler({"Records": [record]}, None), {"batchItemFailures": []})
                # Conflicting metadata on a repeat identity must not mutate the durable item.
                payload.update(external_id="article", content_type="book", duration_minutes=999)
                self.assertEqual(writer.handler({"Records": [{"messageId": "repeat", "body": json.dumps(payload)}]}, None), {"batchItemFailures": []})
                event = {"requestContext": {"http": {"method": "GET"}, "authorizer": {"jwt": {"claims": {"sub": "contract-user"}}}},
                         "queryStringParameters": {"available_minutes": "20"}}
                response = items_api.handler(event, None)
                self.assertEqual(response["statusCode"], 200)
                items = json.loads(response["body"])["content_items"]
                self.assertEqual(len(items), 7)
                self.assertEqual({item["content_type"] for item in items}, items_repository.CONTENT_TYPES)
                self.assertEqual(next(item for item in items if item["content_type"] == "book")["duration_minutes"], 600)
                self.assertEqual(next(item for item in items if item["external_id"] == "article")["duration_minutes"], 1)
                self.assertTrue(all(item["status"] == "active" for item in items))
                self.assertEqual(items_repository.ContentItemRepository().list_for_user("other-user"), [])

            with patch.object(recommendations_repository, "connect", side_effect=connect):
                response = recommendations_api.handler(event, None)
                self.assertEqual(response["statusCode"], 200)
                recommendation = json.loads(response["body"])["recommendation"]
                self.assertEqual(recommendation["action_type"], "consume_content_item")
                self.assertIn(recommendation["content_item"]["content_type"], items_repository.CONTENT_TYPES)
                selected = next(item for item in items if item["id"] == recommendation["content_item"]["id"])
                self.assertEqual(recommendation["estimated_duration_minutes"], selected["duration_minutes"] or 5)

            with engine.begin() as connection:
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                for column, value in (("content_type", None), ("content_type", "audio"), ("duration_minutes", 0), ("duration_minutes", -1)):
                    with self.subTest(column=column, value=value):
                        with self.assertRaises(IntegrityError):
                            with connection.begin_nested():
                                connection.execute(text(f"UPDATE content_items SET {column} = :value WHERE id = :id"), {"value": value, "id": ITEM_ID})
                actions = connection.execute(text("SELECT action_type FROM recommendation_events ORDER BY recommended_at")).scalars().all()
                self.assertEqual(actions, ["read_content_item", "consume_content_item"])
                with Operations.context(MigrationContext.configure(connection)):
                    contract_migration().downgrade()
                self.assertEqual(connection.execute(text("SELECT count(*) FROM content_items")).scalar_one(), 7)
                self.assertEqual(connection.execute(text("SELECT count(*) FROM recommendation_events")).scalar_one(), 2)
        finally:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            engine.dispose()
