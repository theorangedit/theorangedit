"""create promo_campaigns, promo_collections, promotion_log, promotion_prices tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'promo_campaigns',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('link_id', sa.BigInteger(), sa.ForeignKey('links.id', ondelete='CASCADE'), nullable=False),
        sa.Column('owner_id', sa.BigInteger(), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('total_budget_pennies', sa.Integer(), server_default='0', nullable=False),
        sa.Column('bid_pennies', sa.Integer(), server_default='0', nullable=False),
        sa.Column('cost_basis', sa.Integer(), server_default='0', nullable=False),
        sa.Column('adserver_spent_pennies', sa.Integer(), server_default='0', nullable=False),
        sa.Column('priority_name', sa.String(20), server_default='standard', nullable=False),
        sa.Column('trans_id', sa.Integer(), server_default='0', nullable=False),
        sa.Column('trans_ip', sa.Text(), nullable=True),
        sa.Column('trans_ip_country', sa.String(2), nullable=True),
        sa.Column('trans_billing_country', sa.String(2), nullable=True),
        sa.Column('trans_country_match', sa.Boolean(), nullable=True),
        sa.Column('location_code', sa.Text(), nullable=True),
        sa.Column('platform', sa.String(20), server_default='desktop', nullable=False),
        sa.Column('mobile_os_names', sa.Text(), nullable=True),
        sa.Column('ios_device_names', sa.Text(), nullable=True),
        sa.Column('ios_version_names', sa.Text(), nullable=True),
        sa.Column('android_device_names', sa.Text(), nullable=True),
        sa.Column('android_version_names', sa.Text(), nullable=True),
        sa.Column('frequency_cap', sa.Integer(), nullable=True),
        sa.Column('has_served', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('paused', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('target_sr_names', sa.Text(), nullable=True),
        sa.Column('target_name', sa.Text(), nullable=True),
    )
    op.create_index('ix_promo_campaigns_link_id', 'promo_campaigns', ['link_id'])

    op.create_table(
        'promo_collections',
        sa.Column('name', sa.Text(), primary_key=True),
        sa.Column('description', sa.Text(), server_default='', nullable=False),
        sa.Column('sr_names', sa.Text(), server_default='', nullable=False),
        sa.Column('over_18', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_spotlight', sa.Boolean(), server_default='false', nullable=False),
    )

    op.create_table(
        'promotion_log',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('link_fullname', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
    )
    op.create_index('ix_promotion_log_link_fullname', 'promotion_log', ['link_fullname'])

    op.create_table(
        'promotion_prices',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('price_type', sa.String(20), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('cpm_pennies', sa.Integer(), nullable=False),
        sa.UniqueConstraint('price_type', 'name', name='uq_promotion_prices_type_name'),
    )


def downgrade():
    op.drop_table('promotion_prices')
    op.drop_index('ix_promotion_log_link_fullname', 'promotion_log')
    op.drop_table('promotion_log')
    op.drop_table('promo_collections')
    op.drop_index('ix_promo_campaigns_link_id', 'promo_campaigns')
    op.drop_table('promo_campaigns')
