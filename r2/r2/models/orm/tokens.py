from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from r2.models.orm.base import Base


class Token(Base):
    __tablename__ = 'tokens'

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # e.g. 'oauth2_access', 'oauth2_refresh', 'password_reset', 'email_verify'
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=True, index=True
    )
    # Arbitrary token-type-specific fields stored as JSON
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return f'<Token id={self.id[:8]}... type={self.type!r}>'


class OAuthClient(Base):
    __tablename__ = 'oauth_clients'

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    developer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    about_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        __import__('sqlalchemy').Boolean, default=False
    )
    app_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


class OAuthClientDeveloper(Base):
    __tablename__ = 'oauth_client_developers'

    client_id: Mapped[str] = mapped_column(Text, ForeignKey('oauth_clients.id', ondelete='CASCADE'), primary_key=True)
    developer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('accounts.id', ondelete='CASCADE'), primary_key=True)
