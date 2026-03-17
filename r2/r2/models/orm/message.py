from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from r2.models.orm.base import Base


class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fullname: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=False, index=True)
    to_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=False, index=True)
    sr_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('subreddits.id'), nullable=True, index=True)

    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    new: Mapped[bool] = mapped_column(Boolean, default=True)

    # for threaded modmail
    first_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('messages.id'), nullable=True)

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    author = relationship('Account', foreign_keys=[author_id])
    recipient = relationship('Account', foreign_keys=[to_id])
    subreddit = relationship('Subreddit', foreign_keys=[sr_id])

    @property
    def fullname_computed(self) -> str:
        from r2.lib.utils import to36
        return f't4_{to36(self.id)}'

    def __repr__(self) -> str:
        return f'<Message id={self.id} subject={self.subject[:30]!r}>'
