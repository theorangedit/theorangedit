"""
r2.services.ip
~~~~~~~~~~~~~~

Async service layer for IP/account tracking (replaces Cassandra IPsByAccount/AccountsByIP).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.misc import IpTracking

# Match the old Cassandra TTL of 100 days
_DEFAULT_TTL_DAYS = 100


async def record(
    db: AsyncSession,
    account_id: int,
    ip: str,
    date: Optional[datetime] = None,
) -> None:
    from r2.lib.app_globals import g
    if date is None:
        date = datetime.now(g.tz)
    expires_at = date + timedelta(days=_DEFAULT_TTL_DAYS)
    stmt = (
        pg_insert(IpTracking)
        .values(account_id=account_id, ip=ip, date=date, expires_at=expires_at)
        .on_conflict_do_nothing()
    )
    await db.execute(stmt)


async def get_ips_for_account(
    db: AsyncSession,
    account_id: int,
    column_count: int = 100,
) -> list[dict]:
    """Return [{datetime: ip}, ...] most-recent-first, matching old API shape."""
    result = await db.execute(
        select(IpTracking)
        .where(IpTracking.account_id == account_id)
        .order_by(IpTracking.date.desc())
        .limit(column_count)
    )
    return [{row.date: row.ip} for row in result.scalars().all()]


async def get_accounts_for_ip(
    db: AsyncSession,
    ip: str,
    column_count: int = 100,
) -> list[dict]:
    """Return [{datetime: account_id}, ...] most-recent-first, matching old API shape."""
    result = await db.execute(
        select(IpTracking)
        .where(IpTracking.ip == ip)
        .order_by(IpTracking.date.desc())
        .limit(column_count)
    )
    return [{row.date: row.account_id} for row in result.scalars().all()]
