"""create recommendation events table

Revision ID: 20261003_0005
Revises: 20260914_0004
Create Date: 2026-10-03 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261003_0005"
down_revision: Union[str, None] = "20260914_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("available_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.CheckConstraint("available_minutes > 0", name="ck_recommendation_events_available_minutes_positive"),
        sa.CheckConstraint("estimated_duration_minutes > 0", name="ck_recommendation_events_estimated_duration_positive"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], name="fk_recommendation_events_content_item_id_content_items"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_events_user_id_recommended_at", "recommendation_events", ["user_id", "recommended_at"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_events_user_id_recommended_at", table_name="recommendation_events")
    op.drop_table("recommendation_events")
