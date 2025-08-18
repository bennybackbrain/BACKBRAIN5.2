"""add files & summaries & tags tables, extend jobs

Revision ID: 20250817_5_add_files_and_summaries
Revises: 20250817_4_create_users_table
Create Date: 2025-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250817_5_add_files_and_summaries"
# Reference actual revision id defined in create_users_table migration (revision variable)
down_revision = "create_users_table"
branch_labels = None
depends_on = None


def upgrade():
    # files table
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_name", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_files_sha256", "files", ["sha256"])

    # summaries table
    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), index=True, nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("summary_text", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # tags + association
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "file_tags",
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    # extend jobs table: batch for altering existing column nullability; add columns without inline FK then create FK
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("job_type", sa.String(), nullable=False, server_default="entry"))
        batch.add_column(sa.Column("file_id", sa.Integer(), nullable=True))
        batch.alter_column("input_text", existing_type=sa.String(), nullable=True)
        batch.create_foreign_key("fk_jobs_file_id_files", "files", ["file_id"], ["id"])


def downgrade():
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("fk_jobs_file_id_files", type_="foreignkey")
        batch.drop_column("file_id")
        batch.drop_column("job_type")
        batch.alter_column("input_text", existing_type=sa.String(), nullable=False)
    op.drop_table("file_tags")
    op.drop_table("tags")
    op.drop_table("summaries")
    op.drop_index("ix_files_sha256", table_name="files")
    op.drop_table("files")
