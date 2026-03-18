"""create awards and trophies tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'awards',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('codename', sa.String(100), nullable=False),
        sa.Column('title', sa.Text(), nullable=False, server_default=''),
        sa.Column('awardtype', sa.String(20), nullable=False, server_default='regular'),
        sa.Column('imgurl', sa.Text(), nullable=False, server_default=''),
        sa.Column('api_ok', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_awards_codename', 'awards', ['codename'])

    op.create_table(
        'trophies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('award_id', sa.Integer(), sa.ForeignKey('awards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('trophy_url', sa.Text(), nullable=True),
        sa.Column('uid', sa.Text(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_trophies_account_id', 'trophies', ['account_id'])
    op.create_index('ix_trophies_award_id', 'trophies', ['award_id'])
    op.create_index('ix_trophies_date', 'trophies', ['date'])
    # Partial unique index: one trophy per (account, uid) when uid is set.
    # Allows multiple un-keyed trophies (uid IS NULL) per account.
    op.execute(
        "CREATE UNIQUE INDEX trophies_account_uid_uidx "
        "ON trophies (account_id, uid) WHERE uid IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_table('trophies')
    op.drop_table('awards')
