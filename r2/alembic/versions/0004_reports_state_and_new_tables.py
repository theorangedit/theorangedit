"""add state column to report tables; add subreddit_reports and message_reports

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add state column to existing report tables (default 0 = pending)
    op.add_column('link_reports', sa.Column('state', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('comment_reports', sa.Column('state', sa.Integer(), nullable=False, server_default='0'))

    # New report tables
    op.create_table(
        'subreddit_reports',
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('sr_id', sa.BigInteger(), sa.ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('state', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_subreddit_reports_sr_id', 'subreddit_reports', ['sr_id'])
    op.create_index('ix_subreddit_reports_account_id', 'subreddit_reports', ['account_id'])

    op.create_table(
        'message_reports',
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('message_id', sa.BigInteger(), sa.ForeignKey('messages.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('state', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_message_reports_message_id', 'message_reports', ['message_id'])
    op.create_index('ix_message_reports_account_id', 'message_reports', ['account_id'])


def downgrade() -> None:
    op.drop_table('message_reports')
    op.drop_table('subreddit_reports')
    op.drop_column('comment_reports', 'state')
    op.drop_column('link_reports', 'state')
