"""create content sources table

Revision ID: 20260901_0003
Revises: 20260822_0002
Create Date: 2026-09-01 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260901_0003"
down_revision: Union[str, None] = "20260822_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('rss')",
            name="ck_content_sources_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'archived')",
            name="ck_content_sources_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "url", name="uq_content_sources_user_id_url"),
    )
    op.create_index(
        "ix_content_sources_user_id_status",
        "content_sources",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_sources_user_id_status", table_name="content_sources")
    op.drop_table("content_sources")
