"""create user_flair table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_flair',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('sr_id', sa.BigInteger(), sa.ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flair_text', sa.Text(), nullable=True),
        sa.Column('flair_css_class', sa.Text(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('sr_id', 'account_id', name='uq_user_flair_sr_account'),
    )
    op.create_index('ix_user_flair_sr_id', 'user_flair', ['sr_id'])
    op.create_index('ix_user_flair_account_id', 'user_flair', ['account_id'])


def downgrade() -> None:
    op.drop_table('user_flair')
