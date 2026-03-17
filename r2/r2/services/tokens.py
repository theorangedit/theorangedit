"""
Token service — replaces Cassandra Token subclasses.

Covers OAuth2 access/refresh tokens, password reset tokens, and email
verification tokens.  All stored in the `tokens` PostgreSQL table.
"""

from __future__ import annotations

import os
import base64
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.tokens import Token


def _generate_token_id(length: int = 32) -> str:
    """Generate a URL-safe random token id."""
    return base64.urlsafe_b64encode(os.urandom(length)).rstrip(b'=').decode('ascii')


# ── Creation ─────────────────────────────────────────────────────────────────

async def create_token(
    db: AsyncSession,
    token_type: str,
    account_id: Optional[int] = None,
    data: Optional[dict] = None,
    ttl_seconds: Optional[int] = None,
) -> Token:
    expires_at = None
    if ttl_seconds is not None:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

    token = Token(
        id=_generate_token_id(),
        type=token_type,
        account_id=account_id,
        data=data or {},
        expires_at=expires_at,
    )
    db.add(token)
    await db.flush()
    return token


# ── Retrieval / validation ────────────────────────────────────────────────────

async def get_token(
    db: AsyncSession,
    token_id: str,
    token_type: Optional[str] = None,
) -> Optional[Token]:
    """Return a token if it exists and has not expired."""
    stmt = select(Token).where(Token.id == token_id)
    if token_type is not None:
        stmt = stmt.where(Token.type == token_type)

    token = (await db.execute(stmt)).scalar_one_or_none()
    if token is None:
        return None

    if token.expires_at is not None and token.expires_at < datetime.utcnow():
        await revoke_token(db, token_id)
        return None

    return token


async def get_tokens_for_account(
    db: AsyncSession,
    account_id: int,
    token_type: Optional[str] = None,
) -> list[Token]:
    stmt = select(Token).where(Token.account_id == account_id)
    if token_type is not None:
        stmt = stmt.where(Token.type == token_type)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


# ── Revocation ────────────────────────────────────────────────────────────────

async def revoke_token(db: AsyncSession, token_id: str) -> None:
    await db.execute(delete(Token).where(Token.id == token_id))


async def revoke_tokens_for_account(
    db: AsyncSession,
    account_id: int,
    token_type: Optional[str] = None,
) -> None:
    stmt = delete(Token).where(Token.account_id == account_id)
    if token_type is not None:
        stmt = stmt.where(Token.type == token_type)
    await db.execute(stmt)


# ── Expired token cleanup (called by cron) ───────────────────────────────────

async def delete_expired_tokens(db: AsyncSession) -> int:
    """Delete all expired tokens. Returns the number deleted."""
    from sqlalchemy import func
    result = await db.execute(
        delete(Token)
        .where(Token.expires_at != None)
        .where(Token.expires_at < func.now())
    )
    return result.rowcount
