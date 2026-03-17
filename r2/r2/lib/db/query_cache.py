"""
Redis-backed listing/query cache — replaces r2.models.query_cache (Cassandra).

Key conventions (match r2.services.listings):
  listing:sr:{sr_id}:{sort}:{time}          — subreddit link listing
  listing:user:{account_id}:submitted:{sort} — user submissions
  listing:user:{account_id}:comments:{sort}  — user comments
  listing:all:{sort}:{time}                  — /r/all

All operations degrade gracefully when Redis is unavailable — callers
fall back to direct PostgreSQL queries.
"""

from __future__ import annotations

from typing import Optional

from r2.lib.app_globals import g

# ── Cap ──────────────────────────────────────────────────────────────────────

_MAX_CACHED = 1000  # maximum entries per sorted set


# ── Low-level helpers ────────────────────────────────────────────────────────

async def get_listing(
    key: str,
    start: int = 0,
    count: int = 25,
) -> Optional[list[str]]:
    """Return up to *count* fullnames from a Redis sorted set, or None.

    Returns None when Redis is unavailable or the key does not exist.
    """
    redis = getattr(g, 'redis', None)
    if redis is None:
        return None
    try:
        items = await redis.zrevrange(key, start, start + count - 1)
        if not items:
            return None
        return [item.decode() if isinstance(item, bytes) else item for item in items]
    except Exception:
        return None


async def update_listing(
    key: str,
    fullname: str,
    score: float,
    ttl_seconds: Optional[int] = None,
) -> None:
    """Add/update *fullname* in the sorted set and cap it at _MAX_CACHED items.

    Optionally sets a TTL (in seconds) on the key so stale listings expire
    automatically.  TTL is only set when provided and when the zadd succeeds.
    """
    redis = getattr(g, 'redis', None)
    if redis is None:
        return
    try:
        await redis.zadd(key, {fullname: score})
        # Keep only the top _MAX_CACHED by score
        await redis.zremrangebyrank(key, 0, -(_MAX_CACHED + 1))
        if ttl_seconds is not None:
            await redis.expire(key, ttl_seconds)
    except Exception:
        pass


async def remove_from_listing(key: str, fullname: str) -> None:
    """Remove *fullname* from the sorted set."""
    redis = getattr(g, 'redis', None)
    if redis is None:
        return
    try:
        await redis.zrem(key, fullname)
    except Exception:
        pass


async def invalidate_listing(key: str) -> None:
    """Delete an entire listing key (e.g. after a bulk mod action)."""
    redis = getattr(g, 'redis', None)
    if redis is None:
        return
    try:
        await redis.delete(key)
    except Exception:
        pass


# ── Subreddit listing helpers ─────────────────────────────────────────────────

def sr_listing_key(sr_id: int, sort: str, time: str = 'all') -> str:
    return f'listing:sr:{sr_id}:{sort}:{time}'


def all_listing_key(sort: str, time: str = 'all') -> str:
    return f'listing:all:{sort}:{time}'


def user_submitted_key(account_id: int, sort: str) -> str:
    return f'listing:user:{account_id}:submitted:{sort}'


def user_comments_key(account_id: int, sort: str) -> str:
    return f'listing:user:{account_id}:comments:{sort}'


# ── Batch helpers (used by queue consumers) ───────────────────────────────────

async def update_sr_hot(sr_id: int, fullname: str, score: float) -> None:
    for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
        await update_listing(sr_listing_key(sr_id, 'hot', time_key), fullname, score)


async def update_sr_top(sr_id: int, fullname: str, score: float) -> None:
    for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
        await update_listing(sr_listing_key(sr_id, 'top', time_key), fullname, score)


async def update_all_hot(fullname: str, score: float) -> None:
    for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
        await update_listing(all_listing_key('hot', time_key), fullname, score)


async def update_all_top(fullname: str, score: float) -> None:
    for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
        await update_listing(all_listing_key('top', time_key), fullname, score)


async def remove_from_sr(sr_id: int, fullname: str) -> None:
    """Remove a fullname from all sort/time variants of a subreddit listing."""
    for sort in ('hot', 'new', 'top', 'controversial'):
        for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
            await remove_from_listing(sr_listing_key(sr_id, sort, time_key), fullname)


async def remove_from_all(fullname: str) -> None:
    """Remove a fullname from all /r/all listing variants."""
    for sort in ('hot', 'new', 'top', 'controversial'):
        for time_key in ('all', 'year', 'month', 'week', 'day', 'hour'):
            await remove_from_listing(all_listing_key(sort, time_key), fullname)
