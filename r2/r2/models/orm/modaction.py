from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class ModAction(Base):
    __tablename__ = 'mod_actions'
    __table_args__ = (
        Index('ix_mod_actions_sr_date', 'sr_id', 'date'),
        Index('ix_mod_actions_sr_mod_date', 'sr_id', 'mod_id', 'date'),
        Index('ix_mod_actions_sr_action_date', 'sr_id', 'action', 'date'),
        Index('ix_mod_actions_sr_action_mod_date', 'sr_id', 'action', 'mod_id', 'date'),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        server_default=func.gen_random_uuid()
    )
    sr_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('subreddits.id'), nullable=False)
    mod_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id'), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_fullname: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f'<ModAction id={self.id} action={self.action!r} sr_id={self.sr_id}>'
