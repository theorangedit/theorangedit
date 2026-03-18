from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Text, String,
    func, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class PromoCampaign(Base):
    __tablename__ = 'promo_campaigns'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=True)

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Budget / pricing
    total_budget_pennies: Mapped[int] = mapped_column(Integer, default=0)
    bid_pennies: Mapped[int] = mapped_column(Integer, default=0)
    cost_basis: Mapped[int] = mapped_column(Integer, default=0)  # maps to PROMOTE_COST_BASIS enum
    adserver_spent_pennies: Mapped[int] = mapped_column(Integer, default=0)

    # Priority and transaction
    priority_name: Mapped[str] = mapped_column(String(20), default='standard')
    trans_id: Mapped[int] = mapped_column(Integer, default=0)
    trans_ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trans_ip_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    trans_billing_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    trans_country_match: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Geo targeting
    location_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Platform / device targeting
    platform: Mapped[str] = mapped_column(String(20), default='desktop')
    mobile_os_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ios_device_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ios_version_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    android_device_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    android_version_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Frequency / state
    frequency_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_served: Mapped[bool] = mapped_column(Boolean, default=False)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)

    # Subreddit / collection target (pipe-delimited sr names + target type name)
    target_sr_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f'<PromoCampaign id={self.id} link_id={self.link_id}>'


class PromoCollection(Base):
    """Ad-targeting collection of subreddits."""

    __tablename__ = 'promo_collections'

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    sr_names: Mapped[str] = mapped_column(Text, nullable=False, default='')  # pipe-delimited
    over_18: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spotlight: Mapped[bool] = mapped_column(Boolean, default=False)


class PromotionLog(Base):
    """Timestamped log of promotion activity for a link."""

    __tablename__ = 'promotion_log'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    link_fullname: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    text: Mapped[str] = mapped_column(Text, nullable=False)


class PromotionPrices(Base):
    """CPM override prices keyed by (price_type, name).

    price_type is one of: COLLECTION, SUBREDDIT, COUNTRY, METRO
    name is the collection/subreddit/country/metro identifier.
    """

    __tablename__ = 'promotion_prices'
    __table_args__ = (UniqueConstraint('price_type', 'name'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    price_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cpm_pennies: Mapped[int] = mapped_column(Integer, nullable=False)
