"""Derived embedding cache; all access is scoped through owned domain rows."""

from nrt_backend.recommendations.embeddings import MODEL_KEY, validated_vector
from nrt_backend.shared.database import connect

SUBJECTS = {"content_item": ("content_items", "summary"), "goal": ("goals", "description")}


class EmbeddingRepository:
    def load(self, user_id: str, content_item_ids: list[str], goal_ids: list[str]) -> dict:
        result = {}
        # Cache availability must not consume the API's entire request timeout.
        # Writer/operator connections keep the existing database defaults.
        connection = connect(connect_timeout=3, statement_timeout_ms=1000)
        try:
            with connection.cursor() as cursor:
                for kind, ids in (("content_item", content_item_ids), ("goal", goal_ids)):
                    if not ids:
                        continue
                    table, _ = SUBJECTS[kind]
                    cursor.execute(f"""
                        SELECT cache.subject_id, cache.text_hash, cache.vector
                        FROM {kind}_embeddings cache
                        JOIN {table} subject ON subject.id = cache.subject_id
                        WHERE subject.user_id = %s AND cache.model_key = %s
                          AND subject.id = ANY(%s::uuid[])
                    """, (user_id, MODEL_KEY, ids))
                    for subject_id, fingerprint, vector in cursor.fetchall():
                        result[(kind, str(subject_id))] = {"text_hash": fingerprint, "vector": vector}
            return result
        finally:
            connection.close()

    def list_subjects(self, user_id: str, kind: str, limit: int, after_id: str | None = None) -> list[dict]:
        table, detail = SUBJECTS[kind]
        active = "AND subject.status = 'active'" if kind == "goal" else ""
        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT subject.id, subject.title, subject.{detail}, cache.text_hash, cache.vector
                    FROM {table} subject
                    LEFT JOIN {kind}_embeddings cache
                      ON cache.subject_id = subject.id AND cache.model_key = %s
                    WHERE subject.user_id = %s {active}
                      AND (%s::uuid IS NULL OR subject.id > %s::uuid)
                    ORDER BY subject.id LIMIT %s
                """, (MODEL_KEY, user_id, after_id, after_id, limit))
                return [{"id": str(row[0]), "title": row[1], detail: row[2],
                         "cached_hash": row[3], "cached_vector": row[4]} for row in cursor.fetchall()]
        finally:
            connection.close()

    def save(self, user_id: str, kind: str, subject_id: str, fingerprint: str, vector: list[float]):
        table, _ = SUBJECTS[kind]
        vector = validated_vector(vector)
        # Import lazily, matching the existing database runtime dependency pattern.
        from psycopg.types.json import Jsonb

        connection = connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    INSERT INTO {kind}_embeddings (subject_id, model_key, text_hash, vector, created_at)
                    SELECT id, %s, %s, %s, NOW() FROM {table}
                    WHERE id = %s AND user_id = %s
                    ON CONFLICT (subject_id, model_key) DO UPDATE
                    SET text_hash = EXCLUDED.text_hash, vector = EXCLUDED.vector, created_at = NOW()
                """, (MODEL_KEY, fingerprint, Jsonb(vector), subject_id, user_id))
                if cursor.rowcount != 1:
                    raise ValueError("Embedding subject is missing or not owned by user")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
