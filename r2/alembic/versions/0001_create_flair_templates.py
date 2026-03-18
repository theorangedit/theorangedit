"""create flair_templates table

Revision ID: 0001
Revises:
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'flair_templates',
        sa.Column('id', UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('sr_id', sa.BigInteger(), sa.ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flair_type', sa.VARCHAR(10), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('text', sa.Text(), nullable=False, server_default=''),
        sa.Column('css_class', sa.Text(), nullable=False, server_default=''),
        sa.Column('text_editable', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.create_index('ix_flair_templates_sr_id', 'flair_templates', ['sr_id'])
    op.create_unique_constraint(
        'uq_flair_templates_sr_type_pos',
        'flair_templates',
        ['sr_id', 'flair_type', 'position'],
    )


def downgrade() -> None:
    op.drop_table('flair_templates')
