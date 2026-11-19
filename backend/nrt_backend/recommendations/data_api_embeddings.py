"""Data API adapter for background refresh; recommendation reads stay on psycopg."""

import json
import os
import time
from importlib import import_module

from nrt_backend.recommendations.backfill import RefreshInterrupted
from nrt_backend.recommendations.embedding_repository import SUBJECTS
from nrt_backend.recommendations.embeddings import (
    DIMENSIONS,
    MODEL_KEY,
    validated_vector,
)

PAGE_SIZE = 10
TEXT_CHUNK_CHARACTERS = 4000
TRANSIENT_CODES = frozenset({
    "DatabaseResumingException", "DatabaseUnavailableException", "ThrottlingException",
    "TooManyRequestsException", "ServiceUnavailableException", "InternalServerError",
    "InternalServerException", "RequestTimeout", "RequestTimeoutException",
    "ModelNotReadyException", "ModelTimeoutException",
})


def aws_client(service):
    config = import_module("botocore.config").Config(
        # Data API can execute for 45 seconds. A shorter socket timeout retries
        # operations that may still be running. Keep it inside the 90s reserve.
        connect_timeout=2, read_timeout=60 if service == "rds-data" else 10,
        retries={"total_max_attempts": 1},
    )
    return import_module("boto3").client(service, config=config)


def retry_transient(operation, *, check_budget=lambda: None, sleep=time.sleep):
    for attempt in range(3):
        check_budget()
        try:
            return operation()
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            transient = code in TRANSIENT_CODES or isinstance(error, (TimeoutError, ConnectionError)) or type(error).__name__ in {
                "ConnectTimeoutError", "ReadTimeoutError", "EndpointConnectionError", "ConnectionClosedError",
            }
            if not transient or attempt == 2:
                raise
            # A paused Aurora writer commonly needs about 15 seconds to resume.
            sleep((5 if code == "DatabaseResumingException" else 1) * 2 ** attempt)
    raise AssertionError("Retry loop exhausted")


def _parameter(name, value):
    if value is None:
        encoded = {"isNull": True}
    elif isinstance(value, int):
        encoded = {"longValue": value}
    else:
        encoded = {"stringValue": value}
    return {"name": name, "value": encoded}


def _value(field):
    if field == {"isNull": True}:
        return None
    if isinstance(field, dict) and len(field) == 1:
        if isinstance(field.get("stringValue"), str):
            return field["stringValue"]
        if type(field.get("longValue")) is int:
            return field["longValue"]
    raise ValueError("Malformed Data API field")


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class DataApiEmbeddingRepository:
    def __init__(self, client=None, *, check_budget=lambda: None, sleep=time.sleep):
        self.client = client if client is not None else aws_client("rds-data")
        self.check_budget, self.sleep = check_budget, sleep
        self.configuration = {
            "resourceArn": _required_env("DATABASE_CLUSTER_ARN"),
            "secretArn": _required_env("DB_SECRET_ARN"),
            "database": _required_env("DB_NAME"),
        }

    def _execute(self, sql, **parameters):
        response = retry_transient(
            lambda: self.client.execute_statement(
                **self.configuration, sql=sql,
                parameters=[_parameter(name, value) for name, value in parameters.items()],
            ), check_budget=self.check_budget, sleep=self.sleep,
        )
        if not isinstance(response, dict) or not isinstance(response.get("records"), list):
            raise TypeError("Malformed Data API response")
        return [[_value(field) for field in row] for row in response.get("records", [])]

    def list_users(self, limit=PAGE_SIZE, after_user=None):
        if not 1 <= limit <= PAGE_SIZE:
            raise ValueError("Invalid user page size")
        rows = self._execute("""
            SELECT user_id FROM (
                SELECT user_id FROM content_items UNION
                SELECT user_id FROM goals WHERE status = 'active'
            ) owned_users
            WHERE (CAST(:after_user AS text) IS NULL OR user_id > :after_user)
            ORDER BY user_id LIMIT :limit
        """, after_user=after_user, limit=limit)
        if any(len(row) != 1 or not isinstance(row[0], str) or not row[0] for row in rows):
            raise ValueError("Malformed Data API user page")
        return [row[0] for row in rows]

    def list_subjects(self, user_id: str, kind: str, limit: int, after_id: str | None = None):
        """Yield a page lazily so earlier writes survive later hydration failures."""
        if not 1 <= limit <= PAGE_SIZE:
            raise ValueError("Invalid subject page size")
        table, detail = SUBJECTS[kind]
        active = "AND subject.status = 'active'" if kind == "goal" else ""
        # Split the serialized source text, not its semantic representation. A raw
        # HTML prefix may be entirely markup; truncating it would change text-v1.
        rows = self._execute(f"""
            WITH owned AS (
                SELECT subject.id, json_build_object('title', subject.title, '{detail}', subject.{detail})::text AS document,
                       cache.text_hash, cache.vector
                FROM {table} subject LEFT JOIN {kind}_embeddings cache
                  ON cache.subject_id = subject.id AND cache.model_key = :model_key
                WHERE subject.user_id = :user_id {active}
                  AND (CAST(:after_id AS uuid) IS NULL OR subject.id > CAST(:after_id AS uuid))
                ORDER BY subject.id LIMIT :limit
            )
            SELECT id::text, substring(document FROM 1 FOR {TEXT_CHUNK_CHARACTERS}),
                   char_length(document), md5(document), left(text_hash, 128),
                   CASE WHEN jsonb_typeof(vector) = 'array' THEN
                       CASE WHEN jsonb_array_length(vector) = {DIMENSIONS}
                              AND octet_length(vector::text) <= 16000
                              AND NOT EXISTS (
                                  SELECT 1 FROM jsonb_array_elements(vector) entry
                                  WHERE jsonb_typeof(entry) <> 'number'
                              ) THEN vector::text END
                   END
            FROM owned ORDER BY id
        """, model_key=MODEL_KEY, user_id=user_id, after_id=after_id, limit=limit)
        for row in rows:
            if len(row) != 6 or not isinstance(row[0], str):
                raise ValueError("Malformed Data API subject page")
            subject_id, first_chunk, length, source_hash, cached_hash, cached_vector = row
            subject = {"id": subject_id, "cached_hash": cached_hash, "cached_vector": None}
            try:
                if cached_vector is not None:
                    try:
                        subject["cached_vector"] = json.loads(cached_vector)
                    except (TypeError, ValueError):
                        pass  # Invalid cache data is regenerated, not a failed subject.
                chunks = [first_chunk]
                for offset in range(TEXT_CHUNK_CHARACTERS + 1, length + 1, TEXT_CHUNK_CHARACTERS):
                    extra = self._execute(f"""
                        WITH owned AS (
                            SELECT json_build_object('title', subject.title, '{detail}', subject.{detail})::text AS document
                            FROM {table} subject
                            WHERE subject.id = CAST(:subject_id AS uuid) AND subject.user_id = :user_id {active}
                        )
                        SELECT substring(document FROM CAST(:offset AS integer) FOR {TEXT_CHUNK_CHARACTERS})
                        FROM owned WHERE md5(document) = :source_hash
                    """, subject_id=subject_id, user_id=user_id, offset=offset, source_hash=source_hash)
                    if len(extra) != 1 or len(extra[0]) != 1 or not extra[0][0]:
                        raise ValueError("Embedding source changed while reading")
                    chunks.append(extra[0][0])
                subject.update(json.loads("".join(chunks)))
            except RefreshInterrupted:
                raise
            except Exception:  # noqa: BLE001 - one unreadable subject must not hide the rest of a page.
                subject["load_failed"] = True
            yield subject

    def save(self, user_id: str, kind: str, subject_id: str, fingerprint: str, vector: list[float]):
        table, _ = SUBJECTS[kind]
        rows = self._execute(f"""
            INSERT INTO {kind}_embeddings (subject_id, model_key, text_hash, vector, created_at)
            SELECT id, :model_key, :text_hash, CAST(:vector AS jsonb), NOW() FROM {table}
            WHERE id = CAST(:subject_id AS uuid) AND user_id = :user_id
            ON CONFLICT (subject_id, model_key) DO UPDATE
            SET text_hash = EXCLUDED.text_hash, vector = EXCLUDED.vector, created_at = NOW()
            RETURNING subject_id::text
        """, model_key=MODEL_KEY, text_hash=fingerprint, vector=json.dumps(validated_vector(vector)),
            subject_id=subject_id, user_id=user_id)
        if rows != [[subject_id]]:
            raise ValueError("Embedding subject is missing or not owned by user")
