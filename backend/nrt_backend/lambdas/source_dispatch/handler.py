import json
import logging
import os
from importlib import import_module

from nrt_backend.content_sources.repository import ContentSourceRepository


logger = logging.getLogger(__name__)


def handler(event, context):
    queue_url = _required_env("FETCH_JOBS_QUEUE_URL")
    sources = ContentSourceRepository().list_active_rss_sources()
    client = _sqs_client()

    for source in sources:
        job = {
            "user_id": source["user_id"],
            "content_source_id": source["id"],
            "url": source["url"],
        }
        try:
            client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(job))
        except Exception:
            logger.exception(
                "RSS fetch job dispatch failed for content_source_id=%s",
                source["id"],
            )
            raise

    logger.info("RSS source dispatch completed: dispatched=%s", len(sources))


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _sqs_client():
    return import_module("boto3").client("sqs")
