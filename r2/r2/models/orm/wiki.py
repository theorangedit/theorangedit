from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class WikiPage(Base):
    __tablename__ = 'wiki_pages'

    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), primary_key=True)
    page_name: Mapped[str] = mapped_column(Text, primary_key=True)
    content: Mapped[str] = mapped_column(Text, default='')
    revision_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    last_edit_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=True)
    last_edit_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 0=public, 1=wikis only, 2=mods only
    permlevel: Mapped[int] = mapped_column(SmallInteger, default=0)
    listed: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f'<WikiPage sr_id={self.sr_id} page={self.page_name!r}>'


class WikiRevision(Base):
    __tablename__ = 'wiki_revisions'

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        server_default=func.gen_random_uuid()
    )
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'), nullable=False)
    page_name: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=True)
    content: Mapped[str] = mapped_column(Text, default='')
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f'<WikiRevision id={self.id} page={self.page_name!r}>'
