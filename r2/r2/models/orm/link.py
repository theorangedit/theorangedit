from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, String, Text,
    ForeignKey, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from r2.models.orm.base import Base


class Link(Base):
    __tablename__ = 'links'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # fullname is computed but stored for fast lookup: 't3_' + base36(id)
    fullname: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=False, index=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id'), nullable=False, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selftext: Mapped[str] = mapped_column(Text, default='')
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)

    ups: Mapped[int] = mapped_column(Integer, default=1)
    downs: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    gildings: Mapped[int] = mapped_column(Integer, default=0)
    reported: Mapped[int] = mapped_column(Integer, default=0)

    over_18: Mapped[bool] = mapped_column(Boolean, default=False)
    over_18_override: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    disable_comments: Mapped[bool] = mapped_column(Boolean, default=False)
    contest_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    sendreplies: Mapped[bool] = mapped_column(Boolean, default=True)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    ignore_reports: Mapped[bool] = mapped_column(Boolean, default=False)
    moderator_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_before_moderator: Mapped[bool] = mapped_column(Boolean, default=False)
    managed_promo: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_takedown: Mapped[bool] = mapped_column(Boolean, default=False)

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    flair_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flair_css_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    domain_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    suggested_sort: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sticky_comment_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # media
    media_object: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    secure_media_object: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    preview_object: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    media_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_autoplay: Mapped[bool] = mapped_column(Boolean, default=False)

    # promo
    promoted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_flagged_reason: Mapped[str] = mapped_column(Text, default='')
    fraud: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    third_party_tracking: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    third_party_tracking_2: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mobile_ad_url: Mapped[str] = mapped_column(Text, default='')

    # relationships
    author = relationship('Account', foreign_keys=[author_id])
    subreddit = relationship('Subreddit', foreign_keys=[sr_id])

    @property
    def fullname_computed(self) -> str:
        from r2.lib.utils import to36
        return f't3_{to36(self.id)}'

    def __repr__(self) -> str:
        return f'<Link id={self.id} title={self.title[:30]!r}>'
