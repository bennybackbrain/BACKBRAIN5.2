"""add jobs table

Revision ID: add_jobs_table
Revises: 71a43386d921
Create Date: 2025-08-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_jobs_table'
down_revision: Union[str, None] = '71a43386d921'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.Enum('pending','processing','completed','failed', name='jobstatus'), nullable=False),
        sa.Column('input_text', sa.String(), nullable=False),
        sa.Column('result_text', sa.String(), nullable=True),
    )
    op.create_index(op.f('ix_jobs_id'), 'jobs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_id'), table_name='jobs')
    op.drop_table('jobs')
