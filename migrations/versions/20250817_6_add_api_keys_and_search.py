"""add api_keys table

Revision ID: 20250817_6_add_api_keys_and_search
Revises: 20250817_5_add_files_and_summaries
Create Date: 2025-08-17 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20250817_6_add_api_keys_and_search"
down_revision = "20250817_5_add_files_and_summaries"
branch_labels = None
depends_on = None


def upgrade() -> None:  # type: ignore[return-value]
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:  # type: ignore[return-value]
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
