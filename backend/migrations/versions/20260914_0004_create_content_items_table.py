"""create content items table

Revision ID: 20260914_0004
Revises: 20260901_0003
Create Date: 2026-09-14 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260914_0004"
down_revision: Union[str, None] = "20260901_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column(
            "content_source_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_source_id"],
            ["content_sources.id"],
            name="fk_content_items_content_source_id_content_sources",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_source_id",
            "external_id",
            name="uq_content_items_content_source_id_external_id",
        ),
    )
    op.create_index(
        "ix_content_items_user_id_discovered_at",
        "content_items",
        ["user_id", "discovered_at"],
    )
    op.create_index(
        "ix_content_items_content_source_id_published_at",
        "content_items",
        ["content_source_id", "published_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_items_content_source_id_published_at",
        table_name="content_items",
    )
    op.drop_index(
        "ix_content_items_user_id_discovered_at",
        table_name="content_items",
    )
    op.drop_table("content_items")
