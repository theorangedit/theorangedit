from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer,
    SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class VoteDetail(Base):
    """Full vote history for auditing and effects tracking."""
    __tablename__ = 'vote_details'
    __table_args__ = (
        UniqueConstraint('thing_type', 'thing_id', 'voter_id', name='uq_vote_detail'),
        Index('ix_vote_details_thing', 'thing_type', 'thing_id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 'link' or 'comment'
    thing_type: Mapped[str] = mapped_column(String(10), nullable=False)
    thing_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    voter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    direction: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # vote-time effect metadata (karma changes, valid/invalid flags, etc.)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    effects: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class IpTracking(Base):
    """IP addresses associated with accounts (replaces Cassandra IPsByAccount/AccountsByIP)."""
    __tablename__ = 'ip_tracking'
    __table_args__ = (
        Index('ix_ip_tracking_account', 'account_id'),
        Index('ix_ip_tracking_ip', 'ip'),
        Index('ix_ip_tracking_expires', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    ip: Mapped[str] = mapped_column(INET, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # NULL = never expire; otherwise a cron job removes expired rows
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SubredditRule(Base):
    """Subreddit rules (replaces Cassandra SubredditRules)."""
    __tablename__ = 'subreddit_rules'
    __table_args__ = (
        UniqueConstraint('sr_id', 'rule_order', name='uq_sr_rule_order'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False, index=True)
    rule_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    violation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 'all', 'link', 'comment'
    kind: Mapped[str] = mapped_column(String(10), default='all')


class LiveConfig(Base):
    """Replaces ZooKeeper-backed live_config (g.live_config)."""
    __tablename__ = 'live_config'

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
