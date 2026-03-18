"""
r2.services.promo
~~~~~~~~~~~~~~~~~

Async service layer for promoted content: campaigns, collections,
promotion log, and promotion prices.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.promo import (
    PromoCampaign,
    PromoCollection,
    PromotionLog as PromotionLogORM,
    PromotionPrices as PromotionPricesORM,
)


# ---------------------------------------------------------------------------
# PromoCampaign
# ---------------------------------------------------------------------------

async def get_campaign(db: AsyncSession, campaign_id: int) -> Optional[PromoCampaign]:
    result = await db.execute(select(PromoCampaign).where(PromoCampaign.id == campaign_id))
    return result.scalar_one_or_none()


async def get_campaigns(db: AsyncSession, campaign_ids: Sequence[int]) -> dict[int, PromoCampaign]:
    result = await db.execute(
        select(PromoCampaign).where(PromoCampaign.id.in_(campaign_ids))
    )
    return {row.id: row for row in result.scalars().all()}


async def get_campaigns_by_link(db: AsyncSession, link_id: int) -> list[PromoCampaign]:
    result = await db.execute(
        select(PromoCampaign).where(
            PromoCampaign.link_id == link_id,
            PromoCampaign.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def get_campaigns_by_links(db: AsyncSession, link_ids: Sequence[int]) -> list[PromoCampaign]:
    result = await db.execute(
        select(PromoCampaign).where(
            PromoCampaign.link_id.in_(link_ids),
            PromoCampaign.is_deleted == False,
        )
    )
    return list(result.scalars().all())


async def get_campaigns_by_owner(db: AsyncSession, owner_id: int) -> list[PromoCampaign]:
    result = await db.execute(
        select(PromoCampaign).where(PromoCampaign.owner_id == owner_id)
    )
    return list(result.scalars().all())


async def create_campaign(db: AsyncSession, **kwargs) -> PromoCampaign:
    campaign = PromoCampaign(**kwargs)
    db.add(campaign)
    await db.flush()
    return campaign


async def delete_campaign(db: AsyncSession, campaign_id: int) -> None:
    await db.execute(
        update(PromoCampaign)
        .where(PromoCampaign.id == campaign_id)
        .values(is_deleted=True)
    )


# ---------------------------------------------------------------------------
# PromoCollection
# ---------------------------------------------------------------------------

SR_NAMES_DELIM = '|'


async def get_collection(db: AsyncSession, name: str) -> Optional[PromoCollection]:
    result = await db.execute(
        select(PromoCollection).where(PromoCollection.name == name)
    )
    return result.scalar_one_or_none()


async def get_all_collections(db: AsyncSession) -> list[PromoCollection]:
    result = await db.execute(select(PromoCollection))
    return list(result.scalars().all())


async def upsert_collection(
    db: AsyncSession,
    name: str,
    description: str,
    sr_names: list[str],
    over_18: bool = False,
    is_spotlight: bool = False,
) -> PromoCollection:
    sr_names_str = SR_NAMES_DELIM.join(sr_names)
    stmt = (
        pg_insert(PromoCollection)
        .values(name=name, description=description, sr_names=sr_names_str,
                over_18=over_18, is_spotlight=is_spotlight)
        .on_conflict_do_update(
            index_elements=['name'],
            set_={'description': description, 'sr_names': sr_names_str,
                  'over_18': over_18, 'is_spotlight': is_spotlight},
        )
        .returning(PromoCollection)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def update_collection_field(
    db: AsyncSession,
    name: str,
    **fields,
) -> None:
    await db.execute(
        update(PromoCollection).where(PromoCollection.name == name).values(**fields)
    )


async def delete_collection(db: AsyncSession, name: str) -> None:
    await db.execute(delete(PromoCollection).where(PromoCollection.name == name))


# ---------------------------------------------------------------------------
# PromotionLog
# ---------------------------------------------------------------------------

async def add_log_entry(
    db: AsyncSession,
    link_fullname: str,
    text: str,
    created_at: Optional[datetime] = None,
) -> PromotionLogORM:
    entry = PromotionLogORM(
        link_fullname=link_fullname,
        text=text,
        **({"created_at": created_at} if created_at else {}),
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_log_entries(db: AsyncSession, link_fullname: str) -> list[PromotionLogORM]:
    result = await db.execute(
        select(PromotionLogORM)
        .where(PromotionLogORM.link_fullname == link_fullname)
        .order_by(PromotionLogORM.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# PromotionPrices
# ---------------------------------------------------------------------------

async def get_price(db: AsyncSession, price_type: str, name: str) -> Optional[int]:
    result = await db.execute(
        select(PromotionPricesORM.cpm_pennies).where(
            PromotionPricesORM.price_type == price_type,
            PromotionPricesORM.name == name,
        )
    )
    return result.scalar_one_or_none()


async def set_price(db: AsyncSession, price_type: str, name: str, cpm_pennies: int) -> None:
    stmt = (
        pg_insert(PromotionPricesORM)
        .values(price_type=price_type, name=name, cpm_pennies=cpm_pennies)
        .on_conflict_do_update(
            index_elements=['price_type', 'name'],
            set_={'cpm_pennies': cpm_pennies},
        )
    )
    await db.execute(stmt)


async def get_prices_by_type(db: AsyncSession, price_type: str) -> dict[str, int]:
    result = await db.execute(
        select(PromotionPricesORM).where(PromotionPricesORM.price_type == price_type)
    )
    return {row.name: row.cpm_pennies for row in result.scalars().all()}
