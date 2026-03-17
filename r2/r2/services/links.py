"""
Link service — replaces Link Thing ORM calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.lib.app_globals import g
from r2.models.orm.link import Link
from r2.models.orm.relations import LinkVote, LinkSave, LinkHide, LinkVisit, LinkReport

# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_key(link_id: int) -> str:
    return f'link:{link_id}'

def _fullname_cache_key(fullname: str) -> str:
    return f'link_fn:{fullname}'

def _cache_get(link_id: int) -> Optional[Link]:
    if g.thingcache:
        return g.thingcache.get(_cache_key(link_id))
    return None

def _cache_set(link: Link) -> None:
    if g.thingcache:
        g.thingcache.set(_cache_key(link.id), link)
        g.thingcache.set(_fullname_cache_key(link.fullname), link.id)

def _cache_invalidate(link: Link) -> None:
    if g.thingcache:
        g.thingcache.delete(_cache_key(link.id))
        g.thingcache.delete(_fullname_cache_key(link.fullname))


# ── Retrieval ────────────────────────────────────────────────────────────────

async def get_by_id(
    db: AsyncSession,
    link_id: int,
    use_cache: bool = True,
) -> Optional[Link]:
    if use_cache:
        cached = _cache_get(link_id)
        if cached is not None:
            return cached
    result = await db.get(Link, link_id)
    if result is not None:
        _cache_set(result)
    return result


async def get_by_fullname(
    db: AsyncSession,
    fullname: str,
) -> Optional[Link]:
    if g.thingcache:
        cached_id = g.thingcache.get(_fullname_cache_key(fullname))
        if cached_id is not None:
            return await get_by_id(db, cached_id)

    row = (await db.execute(
        select(Link).where(Link.fullname == fullname).limit(1)
    )).scalar_one_or_none()
    if row is not None:
        _cache_set(row)
    return row


async def get_by_ids(
    db: AsyncSession,
    link_ids: list[int],
) -> dict[int, Link]:
    if not link_ids:
        return {}
    result = {}
    missing = []
    for lid in link_ids:
        cached = _cache_get(lid)
        if cached is not None:
            result[lid] = cached
        else:
            missing.append(lid)
    if missing:
        rows = (await db.execute(
            select(Link).where(Link.id.in_(missing))
        )).scalars().all()
        for row in rows:
            _cache_set(row)
            result[row.id] = row
    return result


async def get_by_url(
    db: AsyncSession,
    url: str,
    sr_id: Optional[int] = None,
) -> list[Link]:
    """Find non-deleted links by URL, optionally scoped to a subreddit."""
    stmt = (
        select(Link)
        .where(Link.url == url)
        .where(Link.is_deleted == False)
    )
    if sr_id is not None:
        stmt = stmt.where(Link.sr_id == sr_id)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


# ── Listing queries ──────────────────────────────────────────────────────────

_TIME_FILTERS = {
    'hour':  timedelta(hours=1),
    'day':   timedelta(days=1),
    'week':  timedelta(weeks=1),
    'month': timedelta(days=30),
    'year':  timedelta(days=365),
}


async def get_sr_links(
    db: AsyncSession,
    sr_id: int,
    sort: str = 'hot',
    time: str = 'all',
    limit: int = 25,
    before_id: Optional[int] = None,
) -> list[Link]:
    """Return links for a subreddit listing, sorted and time-filtered."""
    stmt = (
        select(Link)
        .where(Link.sr_id == sr_id)
        .where(Link.is_deleted == False)
        .where(Link.is_spam == False)
    )

    if time != 'all' and time in _TIME_FILTERS:
        cutoff = datetime.utcnow() - _TIME_FILTERS[time]
        stmt = stmt.where(Link.date >= cutoff)

    stmt = _apply_sort(stmt, sort)

    if before_id is not None:
        stmt = stmt.where(Link.id < before_id)

    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    for row in rows:
        _cache_set(row)
    return list(rows)


async def get_user_links(
    db: AsyncSession,
    author_id: int,
    sort: str = 'new',
    time: str = 'all',
    limit: int = 25,
) -> list[Link]:
    """Return links submitted by a user."""
    stmt = (
        select(Link)
        .where(Link.author_id == author_id)
        .where(Link.is_deleted == False)
    )
    if time != 'all' and time in _TIME_FILTERS:
        cutoff = datetime.utcnow() - _TIME_FILTERS[time]
        stmt = stmt.where(Link.date >= cutoff)
    stmt = _apply_sort(stmt, sort).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


def _apply_sort(stmt, sort: str):
    """Apply an ORDER BY clause for the given sort key."""
    from sqlalchemy import desc, func as sa_func, text

    if sort == 'hot':
        return stmt.order_by(desc(sa_func.hot(Link.ups, Link.downs, Link.date)))
    elif sort == 'new':
        return stmt.order_by(desc(Link.date))
    elif sort == 'top':
        return stmt.order_by(desc(sa_func.score(Link.ups, Link.downs)))
    elif sort == 'controversial':
        return stmt.order_by(desc(sa_func.controversy(Link.ups, Link.downs)))
    elif sort == 'rising':
        # Approximate rising: recent links with fast score growth
        return stmt.order_by(desc(Link.ups - Link.downs), desc(Link.date))
    else:
        return stmt.order_by(desc(Link.date))


# ── Votes ────────────────────────────────────────────────────────────────────

async def get_vote(
    db: AsyncSession,
    account_id: int,
    link_id: int,
) -> Optional[int]:
    """Return the vote direction (-1/0/1) or None if no vote exists."""
    row = (await db.execute(
        select(LinkVote.direction)
        .where(LinkVote.account_id == account_id)
        .where(LinkVote.link_id == link_id)
    )).scalar_one_or_none()
    return row


async def cast_vote(
    db: AsyncSession,
    account_id: int,
    link_id: int,
    direction: int,
) -> None:
    """Cast or update a vote on a link. Also updates ups/downs on the link."""
    # Upsert the vote record
    stmt = pg_insert(LinkVote).values(
        account_id=account_id,
        link_id=link_id,
        direction=direction,
    ).on_conflict_do_update(
        index_elements=['account_id', 'link_id'],
        set_={'direction': direction, 'date': func.now()},
    )
    await db.execute(stmt)

    # Recompute ups/downs from the vote table (simple; can be optimized later)
    from sqlalchemy import case
    counts = (await db.execute(
        select(
            func.coalesce(func.sum(case((LinkVote.direction == 1, 1), else_=0)), 0).label('ups'),
            func.coalesce(func.sum(case((LinkVote.direction == -1, 1), else_=0)), 0).label('downs'),
        ).where(LinkVote.link_id == link_id)
    )).one()

    link = await get_by_id(db, link_id, use_cache=False)
    if link:
        link.ups = counts.ups
        link.downs = counts.downs
        await db.flush()
        _cache_invalidate(link)
        _cache_set(link)


# ── Saves / hides ────────────────────────────────────────────────────────────

async def save_link(
    db: AsyncSession,
    account_id: int,
    link_id: int,
    category: Optional[str] = None,
) -> None:
    await db.execute(
        pg_insert(LinkSave).values(
            account_id=account_id, link_id=link_id, category=category
        ).on_conflict_do_nothing()
    )


async def unsave_link(
    db: AsyncSession,
    account_id: int,
    link_id: int,
) -> None:
    await db.execute(
        delete(LinkSave)
        .where(LinkSave.account_id == account_id)
        .where(LinkSave.link_id == link_id)
    )


async def hide_link(
    db: AsyncSession,
    account_id: int,
    link_id: int,
) -> None:
    await db.execute(
        pg_insert(LinkHide).values(
            account_id=account_id, link_id=link_id
        ).on_conflict_do_nothing()
    )


async def unhide_link(
    db: AsyncSession,
    account_id: int,
    link_id: int,
) -> None:
    await db.execute(
        delete(LinkHide)
        .where(LinkHide.account_id == account_id)
        .where(LinkHide.link_id == link_id)
    )


# ── Reports ──────────────────────────────────────────────────────────────────

async def report_link(
    db: AsyncSession,
    account_id: int,
    link_id: int,
    reason: Optional[str] = None,
) -> None:
    await db.execute(
        pg_insert(LinkReport).values(
            account_id=account_id, link_id=link_id, reason=reason
        ).on_conflict_do_nothing()
    )
    # Increment reported count on the link
    link = await get_by_id(db, link_id, use_cache=False)
    if link:
        link.reported += 1
        await db.flush()
        _cache_invalidate(link)
        _cache_set(link)


# ── Creation / editing ───────────────────────────────────────────────────────

async def create_link(
    db: AsyncSession,
    author_id: int,
    sr_id: int,
    title: str,
    url: Optional[str] = None,
    selftext: str = '',
    is_self: bool = False,
    ip: str = '',
    **kwargs,
) -> Link:
    from r2.lib.utils import to36
    # Create the link first to get an id, then set fullname
    link = Link(
        author_id=author_id,
        sr_id=sr_id,
        title=title,
        url=url,
        selftext=selftext,
        is_self=is_self,
        ip=ip,
        fullname='',  # placeholder — set after flush
        **kwargs,
    )
    db.add(link)
    await db.flush()
    link.fullname = f't3_{to36(link.id)}'
    await db.flush()
    _cache_set(link)
    return link


async def edit_selftext(
    db: AsyncSession,
    link: Link,
    new_selftext: str,
) -> Link:
    link.selftext = new_selftext
    await db.flush()
    _cache_invalidate(link)
    _cache_set(link)
    return link


async def delete_link(
    db: AsyncSession,
    link: Link,
) -> None:
    link.is_deleted = True
    await db.flush()
    _cache_invalidate(link)
