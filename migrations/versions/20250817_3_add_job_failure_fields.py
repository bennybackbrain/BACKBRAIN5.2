"""add job failure fields

Revision ID: add_job_failure_fields
Revises: add_jobs_table
Create Date: 2025-08-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'add_job_failure_fields'
down_revision: Union[str, None] = 'add_jobs_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('error_message', sa.String(), nullable=True))
    op.add_column('jobs', sa.Column('retries', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('jobs', 'retries')
    op.drop_column('jobs', 'error_message')
