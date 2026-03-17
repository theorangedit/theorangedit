"""
Listing query service — replaces queries.py CachedQuery/CachedResults system.

Uses Redis sorted sets for pre-computed listing caches (Phase 10), falling
back to direct PostgreSQL queries when cache misses or Redis is unavailable.

Key conventions:
  listing:sr:{sr_id}:{sort}:{time}          — subreddit link listing
  listing:user:{account_id}:submitted:{sort} — user submissions
  listing:user:{account_id}:comments:{sort}  — user comments
  listing:all:{sort}:{time}                  — /r/all
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from r2.lib.app_globals import g
from r2.models.orm.link import Link
from r2.models.orm.comment import Comment

# ── Redis listing helpers ────────────────────────────────────────────────────

async def _redis_get_listing(
    key: str,
    start: int = 0,
    count: int = 25,
) -> Optional[list[str]]:
    """Return fullnames from Redis sorted set, or None if unavailable."""
    if not hasattr(g, 'redis') or g.redis is None:
        return None
    try:
        items = await g.redis.zrevrange(key, start, start + count - 1)
        return [item.decode() if isinstance(item, bytes) else item for item in items]
    except Exception:
        return None


async def _redis_update(key: str, fullname: str, score: float) -> None:
    """Add/update an item in a Redis sorted set, capped at 1000."""
    if not hasattr(g, 'redis') or g.redis is None:
        return
    try:
        await g.redis.zadd(key, {fullname: score})
        await g.redis.zremrangebyrank(key, 0, -1001)
    except Exception:
        pass


async def _redis_remove(key: str, fullname: str) -> None:
    if not hasattr(g, 'redis') or g.redis is None:
        return
    try:
        await g.redis.zrem(key, fullname)
    except Exception:
        pass


# ── Score computation ────────────────────────────────────────────────────────

def _hot_score(ups: int, downs: int, date: datetime) -> float:
    """Python port of the hot() PostgreSQL function for cache building."""
    import math
    s = ups - downs
    sign = 1 if s > 0 else (-1 if s < 0 else 0)
    order = math.log10(max(abs(s), 1))
    seconds = date.timestamp() - 1134028003
    return round(sign * order + seconds / 45000.0, 7)


_TIME_FILTERS = {
    'hour':  timedelta(hours=1),
    'day':   timedelta(days=1),
    'week':  timedelta(weeks=1),
    'month': timedelta(days=30),
    'year':  timedelta(days=365),
}

# ── Public listing API ───────────────────────────────────────────────────────

async def get_sr_links(
    db: AsyncSession,
    sr_id: int,
    sort: str = 'hot',
    time: str = 'all',
    start: int = 0,
    count: int = 25,
) -> list[str]:
    """Return a list of link fullnames for a subreddit listing.

    Tries the Redis cache first; falls back to a PostgreSQL query.
    """
    key = f'listing:sr:{sr_id}:{sort}:{time}'
    cached = await _redis_get_listing(key, start, count)
    if cached is not None:
        return cached

    # PostgreSQL fallback
    links = await _query_sr_links(db, sr_id, sort, time, limit=start + count)
    # Populate cache while we have the data
    for link in links:
        score = _link_score(link, sort)
        await _redis_update(key, link.fullname, score)

    return [l.fullname for l in links[start:start + count]]


async def get_user_submitted(
    db: AsyncSession,
    account_id: int,
    sort: str = 'new',
    time: str = 'all',
    start: int = 0,
    count: int = 25,
) -> list[str]:
    """Return link fullnames for a user's submission history."""
    key = f'listing:user:{account_id}:submitted:{sort}'
    cached = await _redis_get_listing(key, start, count)
    if cached is not None:
        return cached

    links = await _query_user_links(db, account_id, sort, time, limit=start + count)
    for link in links:
        score = _link_score(link, sort)
        await _redis_update(key, link.fullname, score)
    return [l.fullname for l in links[start:start + count]]


async def get_user_comments(
    db: AsyncSession,
    account_id: int,
    sort: str = 'new',
    time: str = 'all',
    start: int = 0,
    count: int = 25,
) -> list[str]:
    """Return comment fullnames for a user's comment history."""
    key = f'listing:user:{account_id}:comments:{sort}'
    cached = await _redis_get_listing(key, start, count)
    if cached is not None:
        return cached

    comments = await _query_user_comments(db, account_id, sort, time, limit=start + count)
    for c in comments:
        score = _comment_score(c, sort)
        await _redis_update(key, c.fullname, score)
    return [c.fullname for c in comments[start:start + count]]


async def get_all_links(
    db: AsyncSession,
    sort: str = 'hot',
    time: str = 'all',
    start: int = 0,
    count: int = 25,
) -> list[str]:
    """/r/all listing."""
    key = f'listing:all:{sort}:{time}'
    cached = await _redis_get_listing(key, start, count)
    if cached is not None:
        return cached

    stmt = _build_link_stmt(sort, time).limit(start + count)
    rows = (await db.execute(stmt)).scalars().all()
    for link in rows:
        score = _link_score(link, sort)
        await _redis_update(key, link.fullname, score)
    return [l.fullname for l in rows[start:start + count]]


# ── Cache mutation (called by queue consumers after vote/post events) ─────────

async def on_new_link(link: Link) -> None:
    """Update listing caches when a new link is submitted."""
    score = _hot_score(link.ups, link.downs, link.date)
    await _redis_update(f'listing:sr:{link.sr_id}:hot:all', link.fullname, score)
    await _redis_update(f'listing:sr:{link.sr_id}:new:all', link.fullname, link.date.timestamp())
    await _redis_update(f'listing:all:hot:all', link.fullname, score)
    await _redis_update(f'listing:all:new:all', link.fullname, link.date.timestamp())
    await _redis_update(f'listing:user:{link.author_id}:submitted:new', link.fullname, link.date.timestamp())


async def on_vote_link(link: Link) -> None:
    """Update hot/top/controversial listing caches after a vote."""
    score_hot = _hot_score(link.ups, link.downs, link.date)
    score_top = link.ups - link.downs

    for time_key in ['all', 'year', 'month', 'week', 'day', 'hour']:
        await _redis_update(f'listing:sr:{link.sr_id}:hot:{time_key}', link.fullname, score_hot)
        await _redis_update(f'listing:sr:{link.sr_id}:top:{time_key}', link.fullname, float(score_top))
        await _redis_update(f'listing:all:hot:{time_key}', link.fullname, score_hot)
        await _redis_update(f'listing:all:top:{time_key}', link.fullname, float(score_top))


async def on_delete_link(link: Link) -> None:
    """Remove a link from listing caches when deleted."""
    for sort in ('hot', 'new', 'top', 'controversial'):
        for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
            await _redis_remove(f'listing:sr:{link.sr_id}:{sort}:{time_key}', link.fullname)
            await _redis_remove(f'listing:all:{sort}:{time_key}', link.fullname)


# ── Internal DB queries ───────────────────────────────────────────────────────

def _build_link_stmt(sort: str, time: str, sr_id: Optional[int] = None):
    from sqlalchemy import desc
    stmt = (
        select(Link)
        .where(Link.is_deleted == False)
        .where(Link.is_spam == False)
    )
    if sr_id is not None:
        stmt = stmt.where(Link.sr_id == sr_id)
    if time != 'all' and time in _TIME_FILTERS:
        cutoff = datetime.utcnow() - _TIME_FILTERS[time]
        stmt = stmt.where(Link.date >= cutoff)

    if sort == 'hot':
        stmt = stmt.order_by(desc(func.hot(Link.ups, Link.downs, Link.date)))
    elif sort == 'new':
        stmt = stmt.order_by(desc(Link.date))
    elif sort == 'top':
        stmt = stmt.order_by(desc(func.score(Link.ups, Link.downs)))
    elif sort == 'controversial':
        stmt = stmt.order_by(desc(func.controversy(Link.ups, Link.downs)))
    else:
        stmt = stmt.order_by(desc(Link.date))
    return stmt


async def _query_sr_links(
    db: AsyncSession,
    sr_id: int,
    sort: str,
    time: str,
    limit: int = 100,
) -> list[Link]:
    stmt = _build_link_stmt(sort, time, sr_id=sr_id).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def _query_user_links(
    db: AsyncSession,
    account_id: int,
    sort: str,
    time: str,
    limit: int = 100,
) -> list[Link]:
    from sqlalchemy import desc
    stmt = (
        select(Link)
        .where(Link.author_id == account_id)
        .where(Link.is_deleted == False)
    )
    if time != 'all' and time in _TIME_FILTERS:
        cutoff = datetime.utcnow() - _TIME_FILTERS[time]
        stmt = stmt.where(Link.date >= cutoff)
    if sort == 'new':
        stmt = stmt.order_by(desc(Link.date))
    elif sort == 'top':
        stmt = stmt.order_by(desc(func.score(Link.ups, Link.downs)))
    else:
        stmt = stmt.order_by(desc(Link.date))
    return list((await db.execute(stmt.limit(limit))).scalars().all())


async def _query_user_comments(
    db: AsyncSession,
    account_id: int,
    sort: str,
    time: str,
    limit: int = 100,
) -> list[Comment]:
    from sqlalchemy import desc
    stmt = (
        select(Comment)
        .where(Comment.author_id == account_id)
        .where(Comment.is_deleted == False)
    )
    if time != 'all' and time in _TIME_FILTERS:
        cutoff = datetime.utcnow() - _TIME_FILTERS[time]
        stmt = stmt.where(Comment.date >= cutoff)
    stmt = stmt.order_by(desc(Comment.date))
    return list((await db.execute(stmt.limit(limit))).scalars().all())


def _link_score(link: Link, sort: str) -> float:
    if sort == 'hot':
        return _hot_score(link.ups, link.downs, link.date)
    elif sort == 'top':
        return float(link.ups - link.downs)
    else:
        return link.date.timestamp()


def _comment_score(comment: Comment, sort: str) -> float:
    if sort == 'top':
        return float(comment.ups - comment.downs)
    return comment.date.timestamp()
