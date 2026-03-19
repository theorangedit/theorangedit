from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Integer, SmallInteger,
    String, Text, ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class SubredditSubscriber(Base):
    __tablename__ = 'subreddit_subscribers'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubredditModerator(Base):
    __tablename__ = 'subreddit_moderators'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    # Bitfield encoding ModeratorPermissionSet permissions
    # bits: 0=access, 1=config, 2=flair, 3=mail, 4=posts, 5=wiki, 6=all (superuser)
    permission_bits: Mapped[int] = mapped_column(Integer, default=0b1111111)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubredditContributor(Base):
    __tablename__ = 'subreddit_contributors'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubredditBanned(Base):
    __tablename__ = 'subreddit_banned'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # NULL duration = permanent ban
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubredditWikibanned(Base):
    __tablename__ = 'subreddit_wikibanned'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubredditWikicontributor(Base):
    __tablename__ = 'subreddit_wikicontributors'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubredditMuted(Base):
    __tablename__ = 'subreddit_muted'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkSave(Base):
    __tablename__ = 'link_saves'
    __table_args__ = (UniqueConstraint('account_id', 'link_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), primary_key=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommentSave(Base):
    __tablename__ = 'comment_saves'
    __table_args__ = (UniqueConstraint('account_id', 'comment_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('comments.id', ondelete='CASCADE'), primary_key=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkHide(Base):
    __tablename__ = 'link_hides'
    __table_args__ = (UniqueConstraint('account_id', 'link_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkVisit(Base):
    __tablename__ = 'link_visits'
    __table_args__ = (UniqueConstraint('account_id', 'link_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkVote(Base):
    __tablename__ = 'link_votes'
    __table_args__ = (UniqueConstraint('account_id', 'link_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), primary_key=True)
    # -1 = downvote, 0 = neutral/removed, 1 = upvote
    direction: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommentVote(Base):
    __tablename__ = 'comment_votes'
    __table_args__ = (UniqueConstraint('account_id', 'comment_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('comments.id', ondelete='CASCADE'), primary_key=True)
    direction: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkReport(Base):
    __tablename__ = 'link_reports'

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # -1 = rejected, 0 = unactioned, 1 = accepted
    state: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommentReport(Base):
    __tablename__ = 'comment_reports'

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('comments.id', ondelete='CASCADE'), primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommentInbox(Base):
    __tablename__ = 'comment_inbox'
    __table_args__ = (UniqueConstraint('account_id', 'comment_id', 'type'),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('comments.id', ondelete='CASCADE'), nullable=False)
    # 'inbox' | 'selfreply' | 'mention'
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageInbox(Base):
    __tablename__ = 'message_inbox'
    __table_args__ = (UniqueConstraint('account_id', 'message_id'),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('messages.id', ondelete='CASCADE'), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BlockedSubreddit(Base):
    __tablename__ = 'blocked_subreddits'
    __table_args__ = (UniqueConstraint('account_id', 'sr_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuarantineOptin(Base):
    """Tracks accounts that have opted in to view quarantined subreddits."""
    __tablename__ = 'quarantine_optins'
    __table_args__ = (UniqueConstraint('account_id', 'sr_id'),)

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionByDay(Base):
    __tablename__ = 'subscription_by_day'
    __table_args__ = (UniqueConstraint('sr_id', 'date'),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, default=0)


class SubredditReport(Base):
    __tablename__ = 'subreddit_reports'

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # -1 = rejected, 0 = unactioned, 1 = accepted
    state: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageReport(Base):
    __tablename__ = 'message_reports'

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('messages.id', ondelete='CASCADE'), primary_key=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserFlair(Base):
    """Per-(subreddit, user) flair assignment."""

    __tablename__ = 'user_flair'
    __table_args__ = (UniqueConstraint('sr_id', 'account_id'),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    flair_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flair_css_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MultiRedditORM(Base):
    __tablename__ = 'multireddits'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default='private')
    key_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    icon_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weighting_scheme: Mapped[str] = mapped_column(String(10), nullable=False, default='classic')
    kind: Mapped[str] = mapped_column(String(1), nullable=False, default='m')
    copied_from: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MultiRedditSubreddit(Base):
    __tablename__ = 'multireddit_subreddits'
    __table_args__ = (UniqueConstraint('multi_id', 'sr_id', name='uq_multi_sr'),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    multi_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('multireddits.id', ondelete='CASCADE'), nullable=False, index=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False)
    sr_props: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default='{}')
