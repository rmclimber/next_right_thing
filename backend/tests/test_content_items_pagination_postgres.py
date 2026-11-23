"""Run only against an explicitly supplied disposable PostgreSQL database."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import psycopg
from sqlalchemy import create_engine, text

from nrt_backend.content_items import repository
from nrt_backend.lambdas.content_items import handler as api


@unittest.skipUnless(os.environ.get("NRT_TEST_DATABASE_URL"), "NRT_TEST_DATABASE_URL is not set")
class ContentItemsPaginationPostgresTests(unittest.TestCase):
    def setUp(self):
        url = os.environ["NRT_TEST_DATABASE_URL"]
        schema = "pagination_" + uuid4().hex
        engine = create_engine(url)
        self.addCleanup(engine.dispose)
        def drop_schema():
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        self.addCleanup(drop_schema)
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config()
            config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
            scripts = ScriptDirectory.from_config(config)
            with Operations.context(MigrationContext.configure(connection)):
                for revision in reversed(list(scripts.walk_revisions(base="base", head="20261116_0008"))):
                    revision.module.upgrade()
        self.connect = lambda: psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"),
                                               options=f"-c search_path={schema}")
        self.enterContext(patch.object(repository, "connect", side_effect=self.connect))
        self.timestamp = datetime(2026, 11, 20, 0, 0, 0, 123456, timezone.utc)
        self.sources = {user: uuid4() for user in ("owner", "other")}
        with self.connect() as connection:
            for user, source in self.sources.items():
                connection.execute("""INSERT INTO content_sources (id, user_id, name, source_type, url, status, created_at, updated_at)
                    VALUES (%s, %s, 'Source', 'rss', %s, 'active', NOW(), NOW())""", (source, user, f"https://example.com/{user}"))

    def seed(self, count, user="owner", start=1, source_user=None):
        with self.connect() as connection:
            for i in range(start, start + count):
                connection.execute("""INSERT INTO content_items (id, user_id, content_source_id, external_id, title, url,
                    summary, discovered_at, created_at, updated_at, content_type, duration_minutes)
                    VALUES (%s, %s, %s, %s, 'Title', 'https://example.com/item', 'Summary', %s, %s, %s, %s, %s)""",
                    (UUID(int=i), user, self.sources[source_user or user], str(i), self.timestamp, self.timestamp,
                     self.timestamp, "podcast_episode" if i % 2 else "article", 42 if i % 2 else None))

    def page(self, user="owner", **query):
        response = api.handler({"requestContext": {"http": {"method": "GET"},
            "authorizer": {"jwt": {"claims": {"sub": user}}}}, "queryStringParameters": query}, None)
        self.assertEqual(response["statusCode"], 200, response)
        return json.loads(response["body"])

    def traverse(self, user="owner", **query):
        items = []
        for _ in range(1000):
            page = self.page(user, **query)
            items.extend(page["content_items"])
            if page["next_cursor"] is None:
                return items
            query["cursor"] = page["next_cursor"]
        self.fail("Traversal did not terminate")

    def test_boundaries_ties_and_exactly_once_traversal(self):
        for count in (0, 1, 49, 50, 51, 100, 101):
            with self.subTest(count=count):
                with self.connect() as connection:
                    connection.execute("DELETE FROM content_items")
                self.seed(count)
                first = self.page()
                self.assertEqual(len(first["content_items"]), min(count, 50))
                self.assertEqual(first["next_cursor"] is None, count <= 50)
                for limit in (1, 50, 100):
                    items = self.traverse(limit=str(limit))
                    self.assertEqual([item["id"] for item in items], [str(UUID(int=i)) for i in range(count, 0, -1)])
                if count:
                    item = first["content_items"][0]
                    self.assertEqual(item["status"], "active")
                    self.assertIsNone(item["snoozed_until"])
                    self.assertNotIn("user_id", item)
                    self.assertEqual(item["summary"], "Summary")
                    self.assertEqual(item["content_type"], "podcast_episode" if count % 2 else "article")

    def test_filters_fill_pages_and_ownership_is_independent_of_position(self):
        self.seed(260)
        self.seed(5, "other", start=1000)
        self.seed(1, start=2000, source_user="other")  # Invalid ownership join must be excluded.
        expected = {"snoozed": [], "completed": [], "archived": []}
        with self.connect() as connection:
            for i in range(1, 211):
                status = ("active", "completed", "archived")[i % 3]
                future = i > 15
                until = datetime.now(timezone.utc) + timedelta(days=1 if future else -1)
                connection.execute("""INSERT INTO content_item_user_state
                    (user_id, content_item_id, status, snoozed_until, created_at, updated_at)
                    VALUES ('owner', %s, %s, %s, NOW(), NOW())""", (UUID(int=i), status, until))
                if status != "active":
                    expected[status].append(str(UUID(int=i)))
                elif future:
                    expected["snoozed"].append(str(UUID(int=i)))
            # Another user's state cannot change an owned item's default state.
            connection.execute("""INSERT INTO content_item_user_state
                (user_id, content_item_id, status, created_at, updated_at)
                VALUES ('other', %s, 'archived', NOW(), NOW())""", (UUID(int=260),))
        for filter, ids in expected.items():
            first = self.page(filter=filter)
            self.assertEqual(len(first["content_items"]), 50)
            self.assertEqual([item["id"] for item in self.traverse(filter=filter)], list(reversed(ids)))
        all_items = self.traverse()
        self.assertEqual(len(all_items), 260)
        self.assertEqual(all_items[0]["status"], "active")
        foreign_cursor = self.page("other", limit="1")["next_cursor"]
        replay = self.traverse(cursor=foreign_cursor)
        self.assertEqual(len(replay), 260)
        position = (self.timestamp, self.timestamp, UUID(int=2001))
        modified = api._encode_cursor(position, "all")
        self.assertEqual(len(self.traverse(cursor=modified)), 260)

    def test_deleted_boundary_new_items_and_current_state(self):
        self.seed(101)
        first = self.page()
        with self.connect() as connection:
            connection.execute("DELETE FROM content_items WHERE id = %s", (UUID(first["content_items"][-1]["id"]),))
        self.seed(1, start=999)
        continued = self.traverse(cursor=first["next_cursor"])
        self.assertEqual([item["id"] for item in continued], [str(UUID(int=i)) for i in range(51, 0, -1)])
        self.assertEqual(self.page()["content_items"][0]["id"], str(UUID(int=999)))
        with self.connect() as connection:
            connection.execute("""INSERT INTO content_item_user_state
                (user_id, content_item_id, status, snoozed_until, created_at, updated_at)
                VALUES ('owner', %s, 'active', NOW() + INTERVAL '1 day', NOW(), NOW())""", (UUID(int=1),))
        self.assertEqual(len(self.page(filter="snoozed")["content_items"]), 1)
        with self.connect() as connection:
            connection.execute("UPDATE content_item_user_state SET snoozed_until = NOW() - INTERVAL '1 second'")
        self.assertEqual(self.page(filter="snoozed")["content_items"], [])
        self.assertEqual(len(self.traverse()), 101)
