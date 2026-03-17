"""
Message service — replaces Message Thing ORM calls and inbox management.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.lib.app_globals import g
from r2.models.orm.message import Message
from r2.models.orm.relations import MessageInbox

# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_key(message_id: int) -> str:
    return f'message:{message_id}'

def _cache_get(message_id: int) -> Optional[Message]:
    if g.thingcache:
        return g.thingcache.get(_cache_key(message_id))
    return None

def _cache_set(msg: Message) -> None:
    if g.thingcache:
        g.thingcache.set(_cache_key(msg.id), msg)

def _cache_invalidate(msg: Message) -> None:
    if g.thingcache:
        g.thingcache.delete(_cache_key(msg.id))


# ── Retrieval ────────────────────────────────────────────────────────────────

async def get_by_id(
    db: AsyncSession,
    message_id: int,
    use_cache: bool = True,
) -> Optional[Message]:
    if use_cache:
        cached = _cache_get(message_id)
        if cached is not None:
            return cached
    result = await db.get(Message, message_id)
    if result is not None:
        _cache_set(result)
    return result


async def get_inbox(
    db: AsyncSession,
    account_id: int,
    unread_only: bool = False,
    limit: int = 25,
) -> list[tuple[Message, MessageInbox]]:
    """Return (Message, MessageInbox) tuples for an account's inbox."""
    stmt = (
        select(Message, MessageInbox)
        .join(MessageInbox, MessageInbox.message_id == Message.id)
        .where(MessageInbox.account_id == account_id)
        .where(Message.is_deleted == False)
    )
    if unread_only:
        stmt = stmt.where(MessageInbox.is_read == False)
    stmt = stmt.order_by(Message.date.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1]) for r in rows]


async def get_sent(
    db: AsyncSession,
    account_id: int,
    limit: int = 25,
) -> list[Message]:
    rows = (await db.execute(
        select(Message)
        .where(Message.author_id == account_id)
        .where(Message.is_deleted == False)
        .order_by(Message.date.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)


# ── Send / mark read ─────────────────────────────────────────────────────────

async def send_message(
    db: AsyncSession,
    author_id: int,
    to_id: int,
    subject: str,
    body: str,
    sr_id: Optional[int] = None,
    first_message_id: Optional[int] = None,
) -> Message:
    from r2.lib.utils import to36
    msg = Message(
        author_id=author_id,
        to_id=to_id,
        subject=subject,
        body=body,
        sr_id=sr_id,
        first_message_id=first_message_id,
        fullname='',
    )
    db.add(msg)
    await db.flush()
    msg.fullname = f't4_{to36(msg.id)}'

    # Add to recipient's inbox
    db.add(MessageInbox(
        account_id=to_id,
        message_id=msg.id,
        is_read=False,
    ))
    await db.flush()
    _cache_set(msg)
    return msg


async def mark_read(
    db: AsyncSession,
    account_id: int,
    message_id: Optional[int] = None,
) -> None:
    """Mark message(s) as read. If message_id is None, mark all."""
    stmt = (
        update(MessageInbox)
        .where(MessageInbox.account_id == account_id)
        .values(is_read=True)
    )
    if message_id is not None:
        stmt = stmt.where(MessageInbox.message_id == message_id)
    await db.execute(stmt)


async def get_unread_count(
    db: AsyncSession,
    account_id: int,
) -> int:
    from sqlalchemy import func
    result = await db.execute(
        select(func.count())
        .select_from(MessageInbox)
        .where(MessageInbox.account_id == account_id)
        .where(MessageInbox.is_read == False)
    )
    return int(result.scalar())
