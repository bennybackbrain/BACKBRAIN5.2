"""add embeddings table

Revision ID: 1c39e24ffdce
Revises: 20250817_7_add_summarizer_usage
Create Date: 2025-08-17 13:51:50.921810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c39e24ffdce'
down_revision: Union[str, None] = '20250817_7_add_summarizer_usage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'embeddings',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id', ondelete='CASCADE'), nullable=True),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('vector', sa.String(), nullable=False),  # JSON string list of floats
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_embeddings_model', 'embeddings', ['model'])
    op.create_index('ix_embeddings_file_id', 'embeddings', ['file_id'])


def downgrade() -> None:
    op.drop_index('ix_embeddings_file_id', table_name='embeddings')
    op.drop_index('ix_embeddings_model', table_name='embeddings')
    op.drop_table('embeddings')
