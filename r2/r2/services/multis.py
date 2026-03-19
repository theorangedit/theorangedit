"""
r2.services.multis
~~~~~~~~~~~~~~~~~~

Pure async SQLAlchemy service functions for multireddits.
No business logic — called by LabeledMulti in r2.models.subreddit.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.relations import MultiRedditORM, MultiRedditSubreddit


async def get_by_path(db: AsyncSession, path: str) -> Optional[MultiRedditORM]:
    result = await db.execute(select(MultiRedditORM).where(MultiRedditORM.path == path))
    return result.scalar_one_or_none()


async def get_by_owner(db: AsyncSession, owner_id: int) -> list[MultiRedditORM]:
    result = await db.execute(
        select(MultiRedditORM).where(MultiRedditORM.owner_id == owner_id)
    )
    return list(result.scalars().all())


async def get_sr_rows(db: AsyncSession, multi_id: int) -> list[MultiRedditSubreddit]:
    result = await db.execute(
        select(MultiRedditSubreddit).where(MultiRedditSubreddit.multi_id == multi_id)
    )
    return list(result.scalars().all())


async def delete_multi(db: AsyncSession, multi_id: int) -> None:
    await db.execute(delete(MultiRedditORM).where(MultiRedditORM.id == multi_id))
    await db.flush()


async def upsert_sr_rows(db: AsyncSession, multi_id: int, sr_id_props: dict) -> None:
    """Replace all subreddit membership rows for a multi.

    sr_id_props: {sr_id: props_dict}
    """
    await db.execute(
        delete(MultiRedditSubreddit).where(MultiRedditSubreddit.multi_id == multi_id)
    )
    for sr_id, props in sr_id_props.items():
        db.add(MultiRedditSubreddit(multi_id=multi_id, sr_id=sr_id, sr_props=props or {}))
    await db.flush()
