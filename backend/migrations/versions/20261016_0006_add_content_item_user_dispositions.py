"""add content item user dispositions

Revision ID: 20261016_0006
Revises: 20261003_0005
Create Date: 2026-10-16 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261016_0006"
down_revision: Union[str, None] = "20261003_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_item_user_state",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'completed', 'archived')", name="ck_content_item_user_state_status"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], name="fk_content_item_user_state_content_item_id_content_items"),
        sa.PrimaryKeyConstraint("user_id", "content_item_id"),
    )
    op.create_table(
        "user_action_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_type IN ('snoozed', 'completed', 'archived')", name="ck_user_action_events_event_type"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], name="fk_user_action_events_content_item_id_content_items"),
        sa.ForeignKeyConstraint(["recommendation_event_id"], ["recommendation_events.id"], name="fk_user_action_events_recommendation_event"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_action_events")
    op.drop_table("content_item_user_state")
