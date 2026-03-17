"""
Moderation service — bans, moderator management, mod log.
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.modaction import ModAction
from r2.models.orm.relations import (
    SubredditBanned,
    SubredditModerator,
    SubredditContributor,
    SubredditWikibanned,
    SubredditWikicontributor,
    SubredditMuted,
)


# ── Moderation checks ────────────────────────────────────────────────────────

async def is_moderator(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
) -> Optional[SubredditModerator]:
    return (await db.execute(
        select(SubredditModerator)
        .where(SubredditModerator.sr_id == sr_id)
        .where(SubredditModerator.account_id == account_id)
    )).scalar_one_or_none()


async def is_banned(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
) -> bool:
    row = (await db.execute(
        select(SubredditBanned)
        .where(SubredditBanned.sr_id == sr_id)
        .where(SubredditBanned.account_id == account_id)
    )).scalar_one_or_none()
    return row is not None


async def is_contributor(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
) -> bool:
    row = (await db.execute(
        select(SubredditContributor)
        .where(SubredditContributor.sr_id == sr_id)
        .where(SubredditContributor.account_id == account_id)
    )).scalar_one_or_none()
    return row is not None


# ── Banning ──────────────────────────────────────────────────────────────────

async def ban_user(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
    note: Optional[str] = None,
    duration: Optional[int] = None,
) -> None:
    await db.execute(
        pg_insert(SubredditBanned).values(
            sr_id=sr_id, account_id=account_id, note=note, duration=duration
        ).on_conflict_do_update(
            index_elements=['sr_id', 'account_id'],
            set_={'note': note, 'duration': duration},
        )
    )


async def unban_user(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
) -> None:
    await db.execute(
        delete(SubredditBanned)
        .where(SubredditBanned.sr_id == sr_id)
        .where(SubredditBanned.account_id == account_id)
    )


# ── Moderator management ─────────────────────────────────────────────────────

async def add_moderator(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
    permission_bits: int = 0b1111111,
) -> None:
    await db.execute(
        pg_insert(SubredditModerator).values(
            sr_id=sr_id,
            account_id=account_id,
            permission_bits=permission_bits,
        ).on_conflict_do_update(
            index_elements=['sr_id', 'account_id'],
            set_={'permission_bits': permission_bits},
        )
    )


async def remove_moderator(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
) -> None:
    await db.execute(
        delete(SubredditModerator)
        .where(SubredditModerator.sr_id == sr_id)
        .where(SubredditModerator.account_id == account_id)
    )


async def update_moderator_permissions(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
    permission_bits: int,
) -> None:
    from sqlalchemy import update
    await db.execute(
        update(SubredditModerator)
        .where(SubredditModerator.sr_id == sr_id)
        .where(SubredditModerator.account_id == account_id)
        .values(permission_bits=permission_bits)
    )


# ── Contributors / wiki ──────────────────────────────────────────────────────

async def add_contributor(db, sr_id, account_id):
    await db.execute(
        pg_insert(SubredditContributor)
        .values(sr_id=sr_id, account_id=account_id)
        .on_conflict_do_nothing()
    )

async def remove_contributor(db, sr_id, account_id):
    await db.execute(
        delete(SubredditContributor)
        .where(SubredditContributor.sr_id == sr_id)
        .where(SubredditContributor.account_id == account_id)
    )

async def wikiban_user(db, sr_id, account_id):
    await db.execute(
        pg_insert(SubredditWikibanned)
        .values(sr_id=sr_id, account_id=account_id)
        .on_conflict_do_nothing()
    )

async def unwikiban_user(db, sr_id, account_id):
    await db.execute(
        delete(SubredditWikibanned)
        .where(SubredditWikibanned.sr_id == sr_id)
        .where(SubredditWikibanned.account_id == account_id)
    )

async def mute_user(db, sr_id, account_id):
    await db.execute(
        pg_insert(SubredditMuted)
        .values(sr_id=sr_id, account_id=account_id)
        .on_conflict_do_nothing()
    )

async def unmute_user(db, sr_id, account_id):
    await db.execute(
        delete(SubredditMuted)
        .where(SubredditMuted.sr_id == sr_id)
        .where(SubredditMuted.account_id == account_id)
    )


# ── Mod log ──────────────────────────────────────────────────────────────────

async def log_action(
    db: AsyncSession,
    sr_id: int,
    mod_id: int,
    action: str,
    target_fullname: Optional[str] = None,
    details: Optional[str] = None,
    description: Optional[str] = None,
) -> ModAction:
    entry = ModAction(
        sr_id=sr_id,
        mod_id=mod_id,
        action=action,
        target_fullname=target_fullname,
        details=details,
        description=description,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_modlog(
    db: AsyncSession,
    sr_id: int,
    mod_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 25,
    before_id: Optional[str] = None,
) -> list[ModAction]:
    stmt = (
        select(ModAction)
        .where(ModAction.sr_id == sr_id)
        .order_by(ModAction.date.desc())
    )
    if mod_id is not None:
        stmt = stmt.where(ModAction.mod_id == mod_id)
    if action is not None:
        stmt = stmt.where(ModAction.action == action)
    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
