"""add multireddits and multireddit_subreddits tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'multireddits',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('path', sa.Text(), nullable=False, unique=True),
        sa.Column('owner_id', sa.BigInteger(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('description_md', sa.Text(), nullable=True),
        sa.Column('visibility', sa.String(10), nullable=False, server_default='private'),
        sa.Column('key_color', sa.String(7), nullable=True),
        sa.Column('icon_id', sa.Text(), nullable=True),
        sa.Column('icon_url', sa.Text(), nullable=True),
        sa.Column('weighting_scheme', sa.String(10), nullable=False, server_default='classic'),
        sa.Column('kind', sa.String(1), nullable=False, server_default='m'),
        sa.Column('copied_from', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_multireddits_path', 'multireddits', ['path'])
    op.create_index('ix_multireddits_owner_id', 'multireddits', ['owner_id'])

    op.create_table(
        'multireddit_subreddits',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('multi_id', sa.BigInteger(), sa.ForeignKey('multireddits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sr_id', sa.BigInteger(), sa.ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sr_props', JSONB(), nullable=False, server_default='{}'),
        sa.UniqueConstraint('multi_id', 'sr_id', name='uq_multi_sr'),
    )
    op.create_index('ix_multireddit_subreddits_multi_id', 'multireddit_subreddits', ['multi_id'])


def downgrade():
    op.drop_table('multireddit_subreddits')
    op.drop_table('multireddits')
