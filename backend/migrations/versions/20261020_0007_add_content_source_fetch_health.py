"""add content source fetch health

Revision ID: 20261020_0007
Revises: 20261016_0006
Create Date: 2026-10-20 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261020_0007"
down_revision: Union[str, None] = "20261016_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_sources", sa.Column("last_fetch_status", sa.Text(), nullable=True))
    op.add_column("content_sources", sa.Column("last_fetch_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_sources", sa.Column("last_fetch_success_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("content_sources", sa.Column("last_fetch_error", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_content_sources_last_fetch_status",
        "content_sources",
        "last_fetch_status IN ('healthy', 'invalid_feed', 'fetch_error')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_content_sources_last_fetch_status", "content_sources", type_="check")
    op.drop_column("content_sources", "last_fetch_error")
    op.drop_column("content_sources", "last_fetch_success_at")
    op.drop_column("content_sources", "last_fetch_attempt_at")
    op.drop_column("content_sources", "last_fetch_status")
