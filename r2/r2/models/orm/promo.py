from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class PromoCampaign(Base):
    __tablename__ = 'promo_campaigns'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('links.id', ondelete='CASCADE'), nullable=False, index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=True)

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    bid: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Flexible storage for campaign-specific fields (targeting, payout data, etc.)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f'<PromoCampaign id={self.id} link_id={self.link_id}>'
