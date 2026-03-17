from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, String, Text,
    ForeignKey, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from r2.models.orm.base import Base

if TYPE_CHECKING:
    from r2.models.orm.relations import AccountKarma


class Account(Base):
    __tablename__ = 'accounts'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text, default='')
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_employee: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # account state
    state: Mapped[int] = mapped_column(Integer, default=0)
    in_timeout: Mapped[bool] = mapped_column(Boolean, default=False)
    ignorereports: Mapped[bool] = mapped_column(Boolean, default=False)
    has_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    has_used_mobile_app: Mapped[bool] = mapped_column(Boolean, default=False)
    disable_karma: Mapped[bool] = mapped_column(Boolean, default=False)

    # gold / special
    gold: Mapped[bool] = mapped_column(Boolean, default=False)
    gold_charter: Mapped[bool] = mapped_column(Boolean, default=False)
    gold_creddits: Mapped[int] = mapped_column(Integer, default=0)
    num_gildings: Mapped[int] = mapped_column(Integer, default=0)
    gild_reveal_username: Mapped[bool] = mapped_column(Boolean, default=False)
    cake_expiration: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # moderation / admin
    report_made: Mapped[int] = mapped_column(Integer, default=0)
    report_correct: Mapped[int] = mapped_column(Integer, default=0)
    report_ignored: Mapped[int] = mapped_column(Integer, default=0)
    spammer: Mapped[int] = mapped_column(Integer, default=0)
    reported: Mapped[int] = mapped_column(Integer, default=0)
    admin_takedown_strikes: Mapped[int] = mapped_column(Integer, default=0)
    banned_profile_visible: Mapped[bool] = mapped_column(Boolean, default=False)

    # messaging
    inbox_count: Mapped[int] = mapped_column(Integer, default=0)
    update_sent_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    modmsgtime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # payment
    num_payment_methods: Mapped[int] = mapped_column(Integer, default=0)
    num_failed_payments: Mapped[int] = mapped_column(Integer, default=0)
    selfserve_cpm_override_pennies: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # security
    otp_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # preferences
    pref_numsites: Mapped[int] = mapped_column(Integer, default=25)
    pref_newwindow: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_clickgadget: Mapped[int] = mapped_column(Integer, default=5)
    pref_store_visits: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_public_votes: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_hide_from_robots: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_research: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_hide_ups: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_hide_downs: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_min_link_score: Mapped[int] = mapped_column(Integer, default=-4)
    pref_min_comment_score: Mapped[int] = mapped_column(Integer, default=-4)
    pref_num_comments: Mapped[int] = mapped_column(Integer, default=200)
    pref_highlight_controversial: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_default_comment_sort: Mapped[str] = mapped_column(String(20), default='confidence')
    pref_lang: Mapped[str] = mapped_column(String(10), default='en')
    pref_over_18: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_compress: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_domain_details: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_organic: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_no_profanity: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_label_nsfw: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_show_stylesheets: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_enable_default_themes: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_default_theme_sr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pref_show_flair: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_show_link_flair: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_mark_messages_read: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_threaded_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_collapse_read_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_email_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_private_feeds: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_force_https: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_hide_ads: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_show_trending: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_highlight_new_comments: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_monitor_mentions: Mapped[bool] = mapped_column(Boolean, default=True)
    pref_collapse_left_bar: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_public_server_seconds: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_ignore_suggested_sort: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_beta: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_legacy_search: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_media: Mapped[str] = mapped_column(String(20), default='subreddit')
    pref_media_preview: Mapped[str] = mapped_column(String(20), default='subreddit')
    pref_use_global_defaults: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_hide_locationbar: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_creddit_autorenew: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_show_snoovatar: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_show_gold_expiration: Mapped[bool] = mapped_column(Boolean, default=False)
    pref_threaded_modmail: Mapped[bool] = mapped_column(Boolean, default=False)

    # mobile preferences
    mobile_compress: Mapped[bool] = mapped_column(Boolean, default=False)
    mobile_thumbnail: Mapped[bool] = mapped_column(Boolean, default=True)

    # wiki override per-account
    wiki_override: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # relationships
    karma: Mapped[list['AccountKarma']] = relationship('AccountKarma', back_populates='account')

    @property
    def fullname(self) -> str:
        return f't2_{self.id}'

    def __repr__(self) -> str:
        return f'<Account id={self.id} name={self.name!r}>'


class AccountKarma(Base):
    __tablename__ = 'account_karma'
    __table_args__ = (
        UniqueConstraint('account_id', 'sr_id', name='uq_account_karma'),
    )

    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    link_karma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_karma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    account: Mapped['Account'] = relationship('Account', back_populates='karma')
