from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from r2.models.orm.base import Base


class Comment(Base):
    __tablename__ = 'comments'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fullname: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=False, index=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id'), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('comments.id'), nullable=True, index=True)

    body: Mapped[str] = mapped_column(Text, nullable=False)

    ups: Mapped[int] = mapped_column(Integer, default=1)
    downs: Mapped[int] = mapped_column(Integer, default=0)
    gildings: Mapped[int] = mapped_column(Integer, default=0)
    reported: Mapped[int] = mapped_column(Integer, default=0)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    sendreplies: Mapped[bool] = mapped_column(Boolean, default=True)
    ignore_reports: Mapped[bool] = mapped_column(Boolean, default=False)
    moderator_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    banned_before_moderator: Mapped[bool] = mapped_column(Boolean, default=False)

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    flair_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    flair_css_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # relationships
    author = relationship('Account', foreign_keys=[author_id])
    link = relationship('Link', foreign_keys=[link_id])
    parent = relationship('Comment', remote_side=[id], foreign_keys=[parent_id])

    @property
    def fullname_computed(self) -> str:
        from r2.lib.utils import to36
        return f't1_{to36(self.id)}'

    def __repr__(self) -> str:
        return f'<Comment id={self.id} link_id={self.link_id}>'
