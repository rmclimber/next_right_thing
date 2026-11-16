"""generalize content item type and known duration

Revision ID: 20261116_0008
Revises: 20261020_0007
Create Date: 2026-11-16 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_0008"
down_revision: Union[str, None] = "20261020_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The default backfills existing rows and also supports an older Writer.
    op.add_column("content_items", sa.Column(
        "content_type", sa.Text(), nullable=False, server_default="article",
    ))
    op.add_column("content_items", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_content_items_content_type", "content_items",
        "content_type IN ('article', 'podcast_episode', 'video', 'research_article', 'book')",
    )
    op.create_check_constraint(
        "ck_content_items_duration_minutes_positive", "content_items",
        "duration_minutes > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_content_items_duration_minutes_positive", "content_items", type_="check")
    op.drop_constraint("ck_content_items_content_type", "content_items", type_="check")
    op.drop_column("content_items", "duration_minutes")
    op.drop_column("content_items", "content_type")
