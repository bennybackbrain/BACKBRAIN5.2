from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '20250817_7_add_summarizer_usage'
down_revision = '20250817_6_add_api_keys_and_search'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'summarizer_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('file_name', sa.String(), nullable=True),
        sa.Column('prefix', sa.String(), nullable=True),
        sa.Column('fallback', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )
    op.create_index('ix_summarizer_usage_created_at', 'summarizer_usage', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_summarizer_usage_created_at', table_name='summarizer_usage')
    op.drop_table('summarizer_usage')
