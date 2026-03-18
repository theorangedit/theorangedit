from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class Award(Base):
    __tablename__ = 'awards'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codename: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default='')
    awardtype: Mapped[str] = mapped_column(String(20), nullable=False, default='regular')
    imgurl: Mapped[str] = mapped_column(Text, nullable=False, default='')
    api_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f'<Award id={self.id} codename={self.codename!r}>'


class Trophy(Base):
    __tablename__ = 'trophies'
    # NOTE: For true deduplication on (account_id, uid) where uid IS NOT NULL,
    # create a PostgreSQL partial unique index in the migration script:
    #   CREATE UNIQUE INDEX trophies_account_uid_uidx
    #     ON trophies (account_id, uid) WHERE uid IS NOT NULL;
    # The UniqueConstraint below enforces uniqueness at the ORM level for
    # rows where uid is provided, but allows multiple NULL uid rows per account.
    __table_args__ = (UniqueConstraint('account_id', 'uid'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    award_id: Mapped[int] = mapped_column(Integer, ForeignKey('awards.id', ondelete='CASCADE'), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trophy_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uid: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return f'<Trophy id={self.id} account_id={self.account_id} award_id={self.award_id}>'
