"""Explicit, resumable embedding refresh. No ingestion or request-time side effects."""

import argparse
import json
import logging
from uuid import UUID

from nrt_backend.recommendations.embedding_repository import EmbeddingRepository
from nrt_backend.recommendations.embeddings import (
    EmbeddingProvider,
    TitanEmbeddingProvider,
    embedding_text,
    text_hash,
    validated_vector,
)

logger = logging.getLogger(__name__)


class RefreshInterrupted(RuntimeError):
    """A bounded refresh must yield before starting more external work."""


def refresh_subject(repository, provider: EmbeddingProvider, user_id: str, kind: str, subject: dict) -> str:
    """Refresh one subject, shared by the operator tool and automatic worker."""
    try:
        if subject.get("load_failed"):
            raise ValueError("Embedding subject could not be read consistently")
        text = embedding_text(subject, kind)
        if not text:
            raise ValueError("Cannot embed empty normalized text")
        fingerprint = text_hash(text)
        if subject.get("cached_hash") == fingerprint:
            try:
                validated_vector(subject.get("cached_vector"))
                return "skipped"
            except ValueError:
                pass
        vector = validated_vector(provider.embed(text))
        repository.save(user_id, kind, subject["id"], fingerprint, vector)
        return "generated"
    except RefreshInterrupted:
        raise
    except Exception as error:  # noqa: BLE001 - isolate provider/storage failure to this subject.
        logger.warning("Embedding refresh failed kind=%s subject_id=%s error_type=%s",
                       kind, subject["id"], type(error).__name__)
        return "failed"


def refresh(repository, provider: EmbeddingProvider, user_id: str, kind: str, limit=100, after_id=None):
    subjects = list(repository.list_subjects(user_id, kind, limit, after_id))
    result = {"scanned": len(subjects), "generated": 0, "skipped": 0, "failed": 0,
              "next_after_id": subjects[-1]["id"] if len(subjects) == limit else None}
    for subject in subjects:
        result[refresh_subject(repository, provider, user_id, kind, subject)] += 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--kind", choices=("content_item", "goal"), required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--after-id", type=UUID)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    result = refresh(EmbeddingRepository(), TitanEmbeddingProvider(), args.user_id, args.kind,
                     args.limit, str(args.after_id) if args.after_id else None)
    print(json.dumps(result))
    # Retry the same page after failures, before advancing its cursor.
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
