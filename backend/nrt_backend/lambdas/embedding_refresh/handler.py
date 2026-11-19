"""Bounded, idempotent refresh outside the VPC; no recommendation-time inference."""

import json
import logging
import os
import time

from nrt_backend.recommendations.backfill import RefreshInterrupted, refresh_subject
from nrt_backend.recommendations.data_api_embeddings import (
    PAGE_SIZE,
    DataApiEmbeddingRepository,
    aws_client,
    retry_transient,
)
from nrt_backend.recommendations.embeddings import TitanEmbeddingProvider

logger = logging.getLogger(__name__)
TIME_RESERVE_MS = 90_000


class RefreshFailed(RuntimeError):
    def __init__(self, summary):
        super().__init__("Embedding refresh incomplete; see embedding_refresh_summary log")
        self.summary = summary


def run_refresh(repository, provider, *, check_budget=lambda: None, max_embeddings=100, sleep=time.sleep):
    summary = {"users": 0, "scanned": 0, "generated": 0, "skipped": 0, "failed": 0,
               "attempted": 0, "remaining_work": False, "stop_reason": None}

    class BoundedProvider:
        def embed(self, text):
            check_budget()
            if summary["attempted"] >= max_embeddings:
                raise RefreshInterrupted("embedding_budget")
            summary["attempted"] += 1
            return retry_transient(lambda: provider.embed(text), check_budget=check_budget, sleep=sleep)

    try:
        after_user = None
        while True:
            check_budget()
            users = repository.list_users(PAGE_SIZE, after_user)
            for user_id in users:
                summary["users"] += 1
                for kind in ("goal", "content_item"):
                    after_id = None
                    while True:
                        check_budget()
                        count = 0
                        for subject in repository.list_subjects(user_id, kind, PAGE_SIZE, after_id):
                            check_budget()
                            status = refresh_subject(repository, BoundedProvider(), user_id, kind, subject)
                            summary[status] += 1
                            summary["scanned"] += 1
                            count += 1
                            after_id = subject["id"]
                        if count < PAGE_SIZE:
                            break
                after_user = user_id
            if len(users) < PAGE_SIZE:
                break
    except RefreshInterrupted as error:
        summary.update(remaining_work=True, stop_reason=str(error))
    except Exception as error:  # noqa: BLE001 - report progress without logging credentials/provider payloads.
        summary.update(remaining_work=True, stop_reason=type(error).__name__)
        summary["failed"] += 1
    if summary["failed"]:
        summary["remaining_work"] = True
        summary["stop_reason"] = summary["stop_reason"] or "subject_failures"
    logger.info("embedding_refresh_summary %s", json.dumps(summary, sort_keys=True))
    if summary["failed"] or summary["remaining_work"]:
        raise RefreshFailed(summary) from None
    return summary


def handler(event, context):
    def check_budget():
        if context.get_remaining_time_in_millis() < TIME_RESERVE_MS:
            raise RefreshInterrupted("time_budget")

    max_embeddings = int(os.environ.get("EMBEDDING_REFRESH_MAX_EMBEDDINGS", "100"))
    if not 1 <= max_embeddings <= 1000:
        raise ValueError("EMBEDDING_REFRESH_MAX_EMBEDDINGS must be between 1 and 1000")
    repository = DataApiEmbeddingRepository(check_budget=check_budget)
    provider = TitanEmbeddingProvider(aws_client("bedrock-runtime"))
    return run_refresh(repository, provider, check_budget=check_budget, max_embeddings=max_embeddings)
