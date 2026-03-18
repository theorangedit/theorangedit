"""
r2.services.flair
~~~~~~~~~~~~~~~~~

Async service layer for per-(subreddit, user) flair assignments.

The ``user_flair`` table stores one row per (sr_id, account_id) pair.
Setting flair upserts the row; setting text and css_class both to None/empty
deletes it.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.relations import UserFlair


async def get_flair(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
) -> Optional[UserFlair]:
    """Return the UserFlair row for *(sr_id, account_id)*, or None."""
    result = await db.execute(
        select(UserFlair).where(
            UserFlair.sr_id == sr_id,
            UserFlair.account_id == account_id,
        )
    )
    return result.scalar_one_or_none()


async def set_flair(
    db: AsyncSession,
    sr_id: int,
    account_id: int,
    flair_text: Optional[str],
    flair_css_class: Optional[str],
) -> Optional[UserFlair]:
    """Upsert flair for *(sr_id, account_id)*.

    If both *flair_text* and *flair_css_class* are empty/None the row is
    deleted and None is returned.  Otherwise the upserted row is returned.
    """
    text = flair_text or None
    css = flair_css_class or None

    if text is None and css is None:
        await db.execute(
            delete(UserFlair).where(
                UserFlair.sr_id == sr_id,
                UserFlair.account_id == account_id,
            )
        )
        return None

    stmt = (
        pg_insert(UserFlair)
        .values(sr_id=sr_id, account_id=account_id, flair_text=text, flair_css_class=css)
        .on_conflict_do_update(
            index_elements=['sr_id', 'account_id'],
            set_={'flair_text': text, 'flair_css_class': css},
        )
        .returning(UserFlair)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def get_flairs_for_sr(
    db: AsyncSession,
    sr_id: int,
    account_ids: Optional[Sequence[int]] = None,
) -> list[UserFlair]:
    """Return all UserFlair rows for *sr_id*, optionally filtered to *account_ids*."""
    q = select(UserFlair).where(UserFlair.sr_id == sr_id)
    if account_ids is not None:
        q = q.where(UserFlair.account_id.in_(account_ids))
    result = await db.execute(q)
    return list(result.scalars().all())
