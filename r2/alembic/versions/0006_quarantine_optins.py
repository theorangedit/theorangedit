"""add quarantine_optins table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'quarantine_optins',
        sa.Column('account_id', sa.BigInteger, sa.ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('sr_id', sa.BigInteger, sa.ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('account_id', 'sr_id', name='uq_quarantine_optins'),
    )


def downgrade() -> None:
    op.drop_table('quarantine_optins')
