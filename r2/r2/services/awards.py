"""
Awards/Trophies service — replaces Cassandra Award/Trophy.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.award import Award as AwardORM, Trophy as TrophyORM


class NotFound(Exception):
    pass


async def get_by_id(db: AsyncSession, award_id: int) -> AwardORM:
    row = (await db.execute(
        select(AwardORM).where(AwardORM.id == award_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFound(f'Award id={award_id!r} not found')
    return row


async def get_by_codename(db: AsyncSession, codename: str) -> AwardORM:
    row = (await db.execute(
        select(AwardORM).where(AwardORM.codename == codename)
    )).scalar_one_or_none()
    if row is None:
        raise NotFound(f'Award codename={codename!r} not found')
    return row


async def get_all(db: AsyncSession) -> list[AwardORM]:
    rows = (await db.execute(
        select(AwardORM).order_by(AwardORM.id)
    )).scalars().all()
    return list(rows)


async def create(
    db: AsyncSession,
    codename: str,
    title: str,
    awardtype: str,
    imgurl: str,
    api_ok: bool,
) -> AwardORM:
    award = AwardORM(
        codename=codename,
        title=title,
        awardtype=awardtype,
        imgurl=imgurl,
        api_ok=api_ok,
    )
    db.add(award)
    await db.flush()
    return award


async def update_award(db: AsyncSession, award_id: int, **fields) -> AwardORM:
    if fields:
        await db.execute(
            update(AwardORM)
            .where(AwardORM.id == award_id)
            .values(**fields)
        )
        await db.flush()
    return await get_by_id(db, award_id)


async def get_trophy(db: AsyncSession, trophy_id: int) -> TrophyORM:
    row = (await db.execute(
        select(TrophyORM).where(TrophyORM.id == trophy_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFound(f'Trophy id={trophy_id!r} not found')
    return row


async def get_trophies_by_account(db: AsyncSession, account_id: int) -> list[TrophyORM]:
    rows = (await db.execute(
        select(TrophyORM)
        .where(TrophyORM.account_id == account_id)
        .order_by(TrophyORM.date.desc())
        .limit(500)
    )).scalars().all()
    return list(rows)


async def get_trophies_by_award(db: AsyncSession, award_id: int) -> list[TrophyORM]:
    rows = (await db.execute(
        select(TrophyORM)
        .where(TrophyORM.award_id == award_id)
        .order_by(TrophyORM.date.desc())
        .limit(50)
    )).scalars().all()
    return list(rows)


async def give_trophy(
    db: AsyncSession,
    account_id: int,
    award_id: int,
    description: Optional[str] = None,
    url: Optional[str] = None,
    trophy_url: Optional[str] = None,
    uid: Optional[str] = None,
) -> TrophyORM:
    trophy = TrophyORM(
        account_id=account_id,
        award_id=award_id,
        description=description,
        url=url,
        trophy_url=trophy_url,
        uid=uid,
    )
    db.add(trophy)
    await db.flush()
    return trophy


async def delete_trophy(db: AsyncSession, trophy_id: int) -> None:
    await db.execute(
        delete(TrophyORM).where(TrophyORM.id == trophy_id)
    )


async def get_trophy_by_uid(db: AsyncSession, account_id: int, uid: str) -> TrophyORM:
    row = (await db.execute(
        select(TrophyORM)
        .where(TrophyORM.account_id == account_id)
        .where(TrophyORM.uid == uid)
    )).scalar_one_or_none()
    if row is None:
        raise NotFound(f'Trophy account_id={account_id!r} uid={uid!r} not found')
    return row
