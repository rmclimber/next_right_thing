"""add derived semantic embedding caches

Revision ID: 20261118_0009
Revises: 20261116_0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261118_0009"
down_revision = "20261116_0008"
branch_labels = None
depends_on = None


def upgrade():
    for kind, table in (("content_item", "content_items"), ("goal", "goals")):
        op.create_table(
            f"{kind}_embeddings",
            sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("model_key", sa.Text(), nullable=False),
            sa.Column("text_hash", sa.Text(), nullable=False),
            sa.Column("vector", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("subject_id", "model_key"),
            sa.ForeignKeyConstraint(["subject_id"], [f"{table}.id"], ondelete="CASCADE"),
            sa.CheckConstraint("jsonb_typeof(vector) = 'array'", name=f"ck_{kind}_embedding_array"),
        )


def downgrade():
    op.drop_table("goal_embeddings")
    op.drop_table("content_item_embeddings")
