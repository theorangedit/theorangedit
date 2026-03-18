from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, Text, UniqueConstraint, VARCHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class FlairTemplate(Base):
    __tablename__ = 'flair_templates'

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        server_default='gen_random_uuid()'
    )
    sr_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('subreddits.id', ondelete='CASCADE'),
        nullable=False, index=True
    )
    flair_type: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False, default='')
    css_class: Mapped[str] = mapped_column(Text, nullable=False, default='')
    text_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint('sr_id', 'flair_type', 'position', name='uq_flair_templates_sr_type_pos'),
    )

    def __repr__(self) -> str:
        return f'<FlairTemplate id={self.id} sr_id={self.sr_id} type={self.flair_type!r} pos={self.position}>'
