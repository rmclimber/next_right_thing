from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from nrt_backend.shared.database import connect


CREATE_CONTENT_SOURCE_SQL = """
INSERT INTO content_sources (
    id,
    user_id,
    name,
    source_type,
    url,
    status,
    created_at,
    updated_at
) VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
)
RETURNING id, name, source_type, url, status, created_at, updated_at;
"""


LIST_CONTENT_SOURCES_SQL = """
SELECT id, name, source_type, url, status, created_at, updated_at
FROM content_sources
WHERE user_id = %s
ORDER BY created_at DESC, id DESC;
"""


@dataclass(frozen=True)
class NewContentSource:
    name: str
    url: str


@dataclass(frozen=True)
class ContentSourceUpdate:
    values: dict


class ContentSourceNotFoundError(Exception):
    pass


class ContentSourceConflictError(Exception):
    pass


class ContentSourceRepository:
    def create(self, user_id: str, new_source: NewContentSource):
        source_id = uuid4()
        now = datetime.now(timezone.utc)
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    CREATE_CONTENT_SOURCE_SQL,
                    (
                        source_id,
                        user_id,
                        new_source.name,
                        "rss",
                        new_source.url,
                        "active",
                        now,
                        now,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()
            return _content_source_from_row(row)
        except Exception as error:
            connection.rollback()
            if _is_unique_url_conflict(error):
                raise ContentSourceConflictError() from error
            raise
        finally:
            connection.close()

    def list_for_user(self, user_id: str):
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(LIST_CONTENT_SOURCES_SQL, (user_id,))
                rows = cursor.fetchall()
            return [_content_source_from_row(row) for row in rows]
        finally:
            connection.close()

    def update_for_user(self, source_id: str, user_id: str, update: ContentSourceUpdate):
        now = datetime.now(timezone.utc)
        assignments = []
        params = []

        for field in ("name", "url", "status"):
            if field in update.values:
                assignments.append(f"{field} = %s")
                params.append(update.values[field])

        assignments.append("updated_at = %s")
        params.extend([now, source_id, user_id])

        query = f"""
UPDATE content_sources
SET {", ".join(assignments)}
WHERE id = %s
AND user_id = %s
RETURNING id, name, source_type, url, status, created_at, updated_at;
"""
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                row = cursor.fetchone()

            if row is None:
                connection.rollback()
                raise ContentSourceNotFoundError()

            connection.commit()
            return _content_source_from_row(row)
        except ContentSourceNotFoundError:
            raise
        except Exception as error:
            connection.rollback()
            if _is_unique_url_conflict(error):
                raise ContentSourceConflictError() from error
            raise
        finally:
            connection.close()


def _is_unique_url_conflict(error):
    if getattr(error, "sqlstate", None) == "23505":
        return True

    diag = getattr(error, "diag", None)
    return getattr(diag, "constraint_name", None) == "uq_content_sources_user_id_url"


def _content_source_from_row(row):
    (
        source_id,
        name,
        source_type,
        url,
        status,
        created_at,
        updated_at,
    ) = row

    return {
        "id": str(source_id) if isinstance(source_id, UUID) else source_id,
        "name": name,
        "source_type": source_type,
        "url": url,
        "status": status,
        "created_at": _datetime_value(created_at),
        "updated_at": _datetime_value(updated_at),
    }


def _datetime_value(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return value
