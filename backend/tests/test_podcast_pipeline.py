"""Real PostgreSQL vertical slice. HTTP, SQS, and Data API health are boundaries."""

from contextlib import ExitStack
from io import BytesIO
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
import psycopg
from sqlalchemy import create_engine, text

from nrt_backend.content_items import repository as items_repository
from nrt_backend.content_sources import repository as sources_repository
from nrt_backend.content_item_state import repository as state_repository
from nrt_backend.recommendations import repository as recommendations_repository
from nrt_backend.lambdas.content_sources import handler as sources_api
from nrt_backend.lambdas.content_items import handler as items_api
from nrt_backend.lambdas.recommendations import handler as recommendations_api
from nrt_backend.lambdas.source_dispatch import handler as dispatch
from nrt_backend.lambdas.rss_fetch import handler as fetch
from nrt_backend.lambdas.content_item_writer import handler as writer


def api_event(method="GET", user="podcast-user", **extra):
    return {"requestContext": {"http": {"method": method},
                               "authorizer": {"jwt": {"claims": {"sub": user}}}}, **extra}


@unittest.skipUnless(os.environ.get("NRT_TEST_DATABASE_URL"), "NRT_TEST_DATABASE_URL is not set")
class PodcastPipelinePostgresTests(unittest.TestCase):
    def setUp(self):
        url = os.environ["NRT_TEST_DATABASE_URL"]
        schema = "podcast_" + uuid4().hex
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

        self.connect = lambda: psycopg.connect(
            url.replace("postgresql+psycopg://", "postgresql://"), options=f"-c search_path={schema}",
        )
        stack = self.enterContext(ExitStack())
        for module in (sources_repository, items_repository, recommendations_repository, state_repository):
            stack.enter_context(patch.object(module, "connect", side_effect=self.connect))

    def test_register_fetch_persist_list_recommend_and_complete_with_duplicate_delivery(self):
        source_response = sources_api.handler(api_event("POST", body=json.dumps({
            "name": "Professional Podcast", "url": "https://example.com/podcast.xml",
        })), None)
        self.assertEqual(source_response["statusCode"], 201)
        source = json.loads(source_response["body"])
        self.assertEqual(source["source_type"], "rss")

        jobs = Mock()
        with patch.dict(os.environ, {"FETCH_JOBS_QUEUE_URL": "https://sqs.example/jobs"}), \
             patch.object(dispatch, "DataApiContentSourceRepository", return_value=sources_repository.ContentSourceRepository()), \
             patch.object(dispatch, "_sqs_client", return_value=jobs):
            dispatch.handler({}, None)
        job = jobs.send_message.call_args.kwargs["MessageBody"]
        self.assertEqual(json.loads(job)["content_source_id"], source["id"])

        feed = (Path(__file__).parent / "fixtures" / "podcast-feed.xml").read_bytes()
        normalized = Mock()
        with patch.dict(os.environ, {"NORMALIZED_CONTENT_ITEMS_QUEUE_URL": "https://sqs.example/items"}), \
             patch.object(fetch, "urlopen", side_effect=lambda *args, **kwargs: BytesIO(feed)), \
             patch.object(fetch, "_record_health") as health, \
             patch.object(fetch, "_sqs_client", return_value=normalized):
            for _ in range(2):
                self.assertEqual(fetch.handler({"Records": [{"messageId": "fetch", "body": job}]}, None), {"batchItemFailures": []})
        self.assertEqual(health.call_count, 2)
        self.assertEqual(normalized.send_message.call_count, 8)
        records = [{"messageId": str(index), "body": call.kwargs["MessageBody"]}
                   for index, call in enumerate(normalized.send_message.call_args_list)]
        for _ in range(2):
            self.assertEqual(writer.handler({"Records": records}, None), {"batchItemFailures": []})

        response = items_api.handler(api_event(), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertIsNone(json.loads(response["body"])["next_cursor"])
        items = json.loads(response["body"])["content_items"]
        self.assertEqual(len(items), 4)
        by_identity = {item["external_id"]: item for item in items}
        episode = by_identity["episode-1"]
        self.assertEqual(episode["content_type"], "podcast_episode")
        self.assertEqual(episode["duration_minutes"], 13)
        self.assertEqual(episode["title"], "Professional learning episode")
        self.assertEqual(episode["summary"], "Episode description")
        self.assertEqual(episode["url"], "https://example.com/audio/1.mp3")
        self.assertEqual(episode["published_at"], "2026-11-18T10:00:00+00:00")
        self.assertEqual(episode["content_source"]["id"], source["id"])
        self.assertTrue(all(item["discovered_at"] for item in items))
        self.assertEqual(by_identity["https://example.com/audio/2.mp3"]["summary"], "Audio-only description")
        self.assertIsNone(by_identity["episode-3"]["published_at"])
        article = by_identity["https://example.com/article"]
        self.assertEqual(article["content_type"], "article")
        self.assertIsNone(article["duration_minutes"])
        self.assertEqual(json.loads(items_api.handler(api_event(user="other-user"), None)["body"])["content_items"], [])

        # Feed correction on a duplicate identity must not mutate persisted metadata.
        corrected = json.loads(records[0]["body"])
        corrected.update(title="Changed title", duration_minutes=99)
        writer.handler({"Records": [{"messageId": "correction", "body": json.dumps(corrected)}]}, None)
        with self.connect() as connection:
            self.assertEqual(connection.execute("SELECT title, duration_minutes FROM content_items WHERE external_id = 'episode-1'").fetchone(),
                             ("Professional learning episode", 13))

        def apply_action(item_id, action, event_id=None):
            result = items_api.handler(api_event("POST", pathParameters={"id": item_id},
                body=json.dumps({"action": action, "recommendation_event_id": event_id})), None)
            self.assertEqual(result["statusCode"], 200)

        # Unknown duration retains the existing five-minute fallback; no new eligibility filter.
        apply_action(article["id"], "archive")
        request = api_event(queryStringParameters={"available_minutes": "10"})
        for _ in range(2):
            result = recommendations_api.handler(request, None)
            self.assertEqual(result["statusCode"], 200)
            recommendation = json.loads(result["body"])["recommendation"]
            self.assertEqual(recommendation["content_item"]["content_type"], "podcast_episode")
            self.assertNotEqual(recommendation["content_item"]["id"], episode["id"])
            self.assertEqual(recommendation["estimated_duration_minutes"], 5)
            apply_action(recommendation["content_item"]["id"], "complete", recommendation["recommendation_event_id"])

        recommendation = json.loads(recommendations_api.handler(request, None)["body"])["recommendation"]
        self.assertEqual(recommendation["content_item"]["id"], episode["id"])
        self.assertEqual(recommendation["action_type"], "consume_content_item")
        self.assertEqual(recommendation["content_item"]["url"], episode["url"])
        self.assertEqual(recommendation["estimated_duration_minutes"], 13)  # Eligible despite exceeding the window by >25%.
        apply_action(episode["id"], "snooze", recommendation["recommendation_event_id"])
        self.assertIsNone(json.loads(recommendations_api.handler(request, None)["body"])["recommendation"])
        apply_action(episode["id"], "complete", recommendation["recommendation_event_id"])
        self.assertIsNone(json.loads(recommendations_api.handler(request, None)["body"])["recommendation"])
        with self.connect() as connection:
            events = connection.execute("SELECT action_type, estimated_duration_minutes FROM recommendation_events").fetchall()
            self.assertEqual(sorted(events), [("consume_content_item", 5), ("consume_content_item", 5), ("consume_content_item", 13)])
