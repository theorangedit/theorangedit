"""
r2.services.rules
~~~~~~~~~~~~~~~~~

Async service layer for subreddit rules.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.misc import SubredditRule

MAX_RULES_PER_SUBREDDIT = 10


async def get_rules(db: AsyncSession, sr_id: int, kind: Optional[str] = None) -> list[SubredditRule]:
    q = (
        select(SubredditRule)
        .where(SubredditRule.sr_id == sr_id)
        .order_by(SubredditRule.rule_order)
    )
    if kind and kind != 'all':
        q = q.where(SubredditRule.kind.in_([kind, 'all']))
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_rule(db: AsyncSession, sr_id: int, short_name: str) -> Optional[SubredditRule]:
    result = await db.execute(
        select(SubredditRule).where(
            SubredditRule.sr_id == sr_id,
            SubredditRule.short_name == short_name,
        )
    )
    return result.scalar_one_or_none()


async def _count_rules(db: AsyncSession, sr_id: int) -> int:
    result = await db.execute(
        select(func.count()).select_from(SubredditRule).where(SubredditRule.sr_id == sr_id)
    )
    return result.scalar_one()


async def create_rule(
    db: AsyncSession,
    sr_id: int,
    short_name: str,
    description: str,
    kind: str = 'all',
) -> Optional[SubredditRule]:
    count = await _count_rules(db, sr_id)
    if count >= MAX_RULES_PER_SUBREDDIT:
        return None
    rule = SubredditRule(
        sr_id=sr_id,
        short_name=short_name,
        description=description,
        kind=kind,
        rule_order=count,
    )
    db.add(rule)
    await db.flush()
    return rule


async def delete_rule(db: AsyncSession, sr_id: int, short_name: str) -> None:
    await db.execute(
        delete(SubredditRule).where(
            SubredditRule.sr_id == sr_id,
            SubredditRule.short_name == short_name,
        )
    )
    remaining = await get_rules(db, sr_id)
    for i, rule in enumerate(remaining):
        rule.rule_order = i
    await db.flush()


async def update_rule(
    db: AsyncSession,
    sr_id: int,
    old_short_name: str,
    short_name: str,
    description: str,
    kind: str = 'all',
) -> bool:
    rule = await get_rule(db, sr_id, old_short_name)
    if not rule:
        return False
    rule.short_name = short_name
    rule.description = description
    rule.kind = kind
    await db.flush()
    return True


async def reorder_rule(db: AsyncSession, sr_id: int, short_name: str, new_order: int) -> bool:
    rule = await get_rule(db, sr_id, short_name)
    if not rule:
        return False
    rules = await get_rules(db, sr_id)
    rules = [r for r in rules if r.short_name != short_name]
    new_order = min(new_order, len(rules))
    rules.insert(new_order, rule)
    for i, r in enumerate(rules):
        r.rule_order = i
    await db.flush()
    return True
