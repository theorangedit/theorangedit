"""
Subreddit service — replaces Subreddit Thing ORM calls.

get_by_name() is on the critical path for every request that includes /r/<name>
in the URL (called from set_subreddit() in reddit_base.py).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from r2.lib.app_globals import g
from r2.models.orm.subreddit import Subreddit

# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_key(sr_id: int) -> str:
    return f'sr:{sr_id}'

def _name_cache_key(name: str) -> str:
    return f'sr_name:{name.lower()}'

def _domain_cache_key(domain: str) -> str:
    return f'sr_domain:{domain.lower()}'

def _cache_get(sr_id: int) -> Optional[Subreddit]:
    if g.thingcache:
        return g.thingcache.get(_cache_key(sr_id))
    return None

def _cache_set(sr: Subreddit) -> None:
    if g.thingcache:
        g.thingcache.set(_cache_key(sr.id), sr)
        g.thingcache.set(_name_cache_key(sr.name), sr.id)

def _cache_invalidate(sr: Subreddit) -> None:
    if g.thingcache:
        g.thingcache.delete(_cache_key(sr.id))
        g.thingcache.delete(_name_cache_key(sr.name))


# ── Retrieval ────────────────────────────────────────────────────────────────

async def get_by_id(
    db: AsyncSession,
    sr_id: int,
    use_cache: bool = True,
) -> Optional[Subreddit]:
    """Return a Subreddit by primary key, or None."""
    if use_cache:
        cached = _cache_get(sr_id)
        if cached is not None:
            return cached

    result = await db.get(Subreddit, sr_id)
    if result is not None:
        _cache_set(result)
    return result


async def get_by_ids(
    db: AsyncSession,
    sr_ids: list[int],
) -> dict[int, Subreddit]:
    """Bulk fetch subreddits by id. Returns {id: Subreddit}."""
    if not sr_ids:
        return {}

    result = {}
    missing = []
    for sid in sr_ids:
        cached = _cache_get(sid)
        if cached is not None:
            result[sid] = cached
        else:
            missing.append(sid)

    if missing:
        rows = (await db.execute(
            select(Subreddit).where(Subreddit.id.in_(missing))
        )).scalars().all()
        for row in rows:
            _cache_set(row)
            result[row.id] = row

    return result


async def get_by_name(
    db: AsyncSession,
    name: str,
    stale: bool = False,
) -> Optional[Subreddit]:
    """Return a Subreddit by name (case-insensitive), or None.

    `stale=True` allows returning a cached value without a freshness check
    (matches the legacy Subreddit._by_name(name, stale=True) behaviour).
    """
    name_lower = name.lower()

    if g.thingcache:
        cached_id = g.thingcache.get(_name_cache_key(name_lower))
        if cached_id is not None:
            cached = _cache_get(cached_id)
            if cached is not None:
                return cached

    stmt = (
        select(Subreddit)
        .where(func.lower(Subreddit.name) == name_lower)
        .where(Subreddit.is_deleted == False)
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is not None:
        _cache_set(row)
    return row


async def get_by_names(
    db: AsyncSession,
    names: list[str],
) -> dict[str, Subreddit]:
    """Bulk fetch subreddits by name. Returns {lowercase_name: Subreddit}."""
    if not names:
        return {}

    names_lower = [n.lower() for n in names]
    result = {}
    missing = []

    for n in names_lower:
        if g.thingcache:
            cached_id = g.thingcache.get(_name_cache_key(n))
            if cached_id is not None:
                cached = _cache_get(cached_id)
                if cached is not None:
                    result[n] = cached
                    continue
        missing.append(n)

    if missing:
        rows = (await db.execute(
            select(Subreddit)
            .where(func.lower(Subreddit.name).in_(missing))
            .where(Subreddit.is_deleted == False)
        )).scalars().all()
        for row in rows:
            _cache_set(row)
            result[row.name.lower()] = row

    return result


async def get_by_domain(
    db: AsyncSession,
    domain: str,
) -> Optional[Subreddit]:
    """Return the subreddit mapped to a custom domain, or None."""
    domain_lower = domain.lower()

    if g.thingcache:
        cached_id = g.thingcache.get(_domain_cache_key(domain_lower))
        if cached_id is not None:
            return await get_by_id(db, cached_id)

    stmt = (
        select(Subreddit)
        .where(func.lower(Subreddit.domain) == domain_lower)
        .where(Subreddit.is_deleted == False)
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is not None:
        _cache_set(row)
        if g.thingcache:
            g.thingcache.set(_domain_cache_key(domain_lower), row.id)
    return row


# ── Membership ───────────────────────────────────────────────────────────────

async def get_subscriptions(
    db: AsyncSession,
    account_id: int,
) -> list[Subreddit]:
    """Return all subreddits the account is subscribed to."""
    from r2.models.orm.relations import SubredditSubscriber
    stmt = (
        select(Subreddit)
        .join(SubredditSubscriber, SubredditSubscriber.sr_id == Subreddit.id)
        .where(SubredditSubscriber.account_id == account_id)
        .where(Subreddit.is_deleted == False)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def subscribe(
    db: AsyncSession,
    account_id: int,
    sr_id: int,
) -> None:
    """Subscribe an account to a subreddit (idempotent)."""
    from r2.models.orm.relations import SubredditSubscriber
    stmt = pg_insert(SubredditSubscriber).values(
        account_id=account_id, sr_id=sr_id
    ).on_conflict_do_nothing()
    await db.execute(stmt)


async def unsubscribe(
    db: AsyncSession,
    account_id: int,
    sr_id: int,
) -> None:
    """Unsubscribe an account from a subreddit."""
    from r2.models.orm.relations import SubredditSubscriber
    from sqlalchemy import delete
    await db.execute(
        delete(SubredditSubscriber)
        .where(SubredditSubscriber.account_id == account_id)
        .where(SubredditSubscriber.sr_id == sr_id)
    )


async def get_moderators(
    db: AsyncSession,
    sr_id: int,
) -> list[int]:
    """Return account_ids of all moderators of a subreddit, ordered by date."""
    from r2.models.orm.relations import SubredditModerator
    rows = (await db.execute(
        select(SubredditModerator.account_id)
        .where(SubredditModerator.sr_id == sr_id)
        .order_by(SubredditModerator.date)
    )).scalars().all()
    return list(rows)


# ── Creation / updates ───────────────────────────────────────────────────────

async def create_subreddit(
    db: AsyncSession,
    name: str,
    title: str,
    creator_id: int,
    **kwargs,
) -> Subreddit:
    """Create a new subreddit and make creator its first moderator."""
    from r2.models.orm.relations import SubredditModerator

    sr = Subreddit(name=name, title=title, **kwargs)
    db.add(sr)
    await db.flush()  # populate sr.id

    # Creator becomes superuser moderator (all permission bits set)
    db.add(SubredditModerator(
        sr_id=sr.id,
        account_id=creator_id,
        permission_bits=0b1111111,
    ))
    await db.flush()

    _cache_set(sr)
    return sr


async def update_subreddit(
    db: AsyncSession,
    sr: Subreddit,
    **kwargs,
) -> Subreddit:
    """Update arbitrary subreddit fields."""
    for key, value in kwargs.items():
        setattr(sr, key, value)
    await db.flush()
    _cache_invalidate(sr)
    _cache_set(sr)
    return sr


# ── Missing import ────────────────────────────────────────────────────────────

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
