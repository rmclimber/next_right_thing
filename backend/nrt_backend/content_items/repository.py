from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from nrt_backend.shared.database import connect


INSERT_CONTENT_ITEM_SQL = """
WITH owned_source AS (
    SELECT id
    FROM content_sources
    WHERE id = %s
    AND user_id = %s
), inserted AS (
    INSERT INTO content_items (
        id,
        user_id,
        content_source_id,
        external_id,
        title,
        url,
        summary,
        published_at,
        discovered_at,
        created_at,
        updated_at
    )
    SELECT
        %s,
        %s,
        owned_source.id,
        %s,
        %s,
        %s,
        %s,
        %s,
        %s,
        %s,
        %s
    FROM owned_source
    ON CONFLICT (content_source_id, external_id) DO NOTHING
    RETURNING id
)
SELECT
    EXISTS (SELECT 1 FROM owned_source) AS source_owned,
    EXISTS (SELECT 1 FROM inserted) AS inserted;
"""


LIST_CONTENT_ITEMS_SQL = """
SELECT
    id,
    content_source_id,
    external_id,
    title,
    url,
    summary,
    published_at,
    discovered_at,
    created_at,
    updated_at
FROM content_items
WHERE user_id = %s
ORDER BY discovered_at DESC, created_at DESC, id DESC;
"""


class ContentSourceOwnershipError(ValueError):
    """Raised when a Content Source is not owned by the message user."""


@dataclass(frozen=True)
class NewContentItem:
    user_id: str
    content_source_id: UUID
    external_id: str
    title: str
    url: str
    summary: str | None
    published_at: datetime | None
    discovered_at: datetime


class ContentItemRepository:
    def create(self, item: NewContentItem) -> bool:
        """Persist an item and return whether this delivery created a row."""
        now = datetime.now(timezone.utc)
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    INSERT_CONTENT_ITEM_SQL,
                    (
                        item.content_source_id,
                        item.user_id,
                        uuid4(),
                        item.user_id,
                        item.external_id,
                        item.title,
                        item.url,
                        item.summary,
                        item.published_at,
                        item.discovered_at,
                        now,
                        now,
                    ),
                )
                source_owned, inserted = cursor.fetchone()
            connection.commit()

            if not source_owned:
                raise ContentSourceOwnershipError(
                    "content_source_id does not belong to user_id"
                )

            return inserted
        except ContentSourceOwnershipError:
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_for_user(self, user_id: str):
        connection = connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(LIST_CONTENT_ITEMS_SQL, (user_id,))
                rows = cursor.fetchall()
            return [_content_item_from_row(row) for row in rows]
        finally:
            connection.close()


def _content_item_from_row(row):
    (
        item_id,
        content_source_id,
        external_id,
        title,
        url,
        summary,
        published_at,
        discovered_at,
        created_at,
        updated_at,
    ) = row

    return {
        "id": _uuid_value(item_id),
        "content_source_id": _uuid_value(content_source_id),
        "external_id": external_id,
        "title": title,
        "url": url,
        "summary": summary,
        "published_at": _datetime_value(published_at),
        "discovered_at": _datetime_value(discovered_at),
        "created_at": _datetime_value(created_at),
        "updated_at": _datetime_value(updated_at),
    }


def _uuid_value(value):
    return str(value) if isinstance(value, UUID) else value


def _datetime_value(value):
    return value.isoformat() if isinstance(value, datetime) else value
