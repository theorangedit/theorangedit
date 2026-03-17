from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class Subreddit(Base):
    __tablename__ = 'subreddits'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(21), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, default='')
    description: Mapped[str] = mapped_column(Text, default='')
    public_description: Mapped[str] = mapped_column(Text, default='')
    submit_text: Mapped[str] = mapped_column(Text, default='')
    sidebar: Mapped[str] = mapped_column(Text, default='')

    type: Mapped[str] = mapped_column(String(20), default='public', nullable=False)
    lang: Mapped[str] = mapped_column(String(10), default='en', nullable=False)
    over_18: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # appearance / settings
    header_title: Mapped[str] = mapped_column(Text, default='')
    stylesheet_url: Mapped[str] = mapped_column(Text, default='')
    stylesheet_url_http: Mapped[str] = mapped_column(Text, default='')
    stylesheet_url_https: Mapped[str] = mapped_column(Text, default='')
    domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    login_required: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_top: Mapped[bool] = mapped_column(Boolean, default=False)
    show_media: Mapped[bool] = mapped_column(Boolean, default=False)
    show_media_preview: Mapped[bool] = mapped_column(Boolean, default=True)
    public_traffic: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_ads: Mapped[bool] = mapped_column(Boolean, default=False)
    quarantine: Mapped[bool] = mapped_column(Boolean, default=False)

    # icon / banner
    icon_img: Mapped[str] = mapped_column(Text, default='')
    icon_size: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    banner_img: Mapped[str] = mapped_column(Text, default='')
    banner_size: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    key_color: Mapped[str] = mapped_column(String(10), default='')

    # moderation settings
    exclude_banned_modqueue: Mapped[bool] = mapped_column(Boolean, default=False)
    spam_links: Mapped[str] = mapped_column(String(10), default='high')
    spam_selfposts: Mapped[str] = mapped_column(String(10), default='high')
    spam_comments: Mapped[str] = mapped_column(String(10), default='low')
    mod_actions: Mapped[int] = mapped_column(Integer, default=0)
    ban_count: Mapped[int] = mapped_column(Integer, default=0)
    reported: Mapped[int] = mapped_column(Integer, default=0)
    valid_votes: Mapped[int] = mapped_column(Integer, default=0)

    # submission settings
    link_type: Mapped[str] = mapped_column(String(10), default='any')
    submit_link_label: Mapped[str] = mapped_column(Text, default='')
    submit_text_label: Mapped[str] = mapped_column(Text, default='')
    suggested_comment_sort: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # flair
    flair_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    flair_position: Mapped[str] = mapped_column(String(10), default='right')
    link_flair_position: Mapped[str] = mapped_column(String(10), default='')
    flair_self_assign_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    link_flair_self_assign_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # wiki
    wikimode: Mapped[str] = mapped_column(String(20), default='disabled')
    wiki_edit_karma: Mapped[int] = mapped_column(Integer, default=100)
    wiki_edit_age: Mapped[int] = mapped_column(Integer, default=0)

    # comments
    comment_score_hide_mins: Mapped[int] = mapped_column(Integer, default=0)
    collapse_deleted_comments: Mapped[bool] = mapped_column(Boolean, default=False)
    contest_mode_upvotes_only: Mapped[bool] = mapped_column(Boolean, default=False)

    # misc
    use_quotas: Mapped[bool] = mapped_column(Boolean, default=True)
    archive_age: Mapped[int] = mapped_column(Integer, default=182)
    gilding_server_seconds: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def fullname(self) -> str:
        return f't5_{self.id}'

    def __repr__(self) -> str:
        return f'<Subreddit id={self.id} name={self.name!r}>'
