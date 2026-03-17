"""
Comment service — replaces Comment Thing ORM calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.lib.app_globals import g
from r2.models.orm.comment import Comment
from r2.models.orm.relations import CommentVote, CommentSave, CommentReport, CommentInbox

# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_key(comment_id: int) -> str:
    return f'comment:{comment_id}'

def _cache_get(comment_id: int) -> Optional[Comment]:
    if g.thingcache:
        return g.thingcache.get(_cache_key(comment_id))
    return None

def _cache_set(comment: Comment) -> None:
    if g.thingcache:
        g.thingcache.set(_cache_key(comment.id), comment)

def _cache_invalidate(comment: Comment) -> None:
    if g.thingcache:
        g.thingcache.delete(_cache_key(comment.id))


# ── Retrieval ────────────────────────────────────────────────────────────────

async def get_by_id(
    db: AsyncSession,
    comment_id: int,
    use_cache: bool = True,
) -> Optional[Comment]:
    if use_cache:
        cached = _cache_get(comment_id)
        if cached is not None:
            return cached
    result = await db.get(Comment, comment_id)
    if result is not None:
        _cache_set(result)
    return result


async def get_by_ids(
    db: AsyncSession,
    comment_ids: list[int],
) -> dict[int, Comment]:
    if not comment_ids:
        return {}
    result = {}
    missing = []
    for cid in comment_ids:
        cached = _cache_get(cid)
        if cached is not None:
            result[cid] = cached
        else:
            missing.append(cid)
    if missing:
        rows = (await db.execute(
            select(Comment).where(Comment.id.in_(missing))
        )).scalars().all()
        for row in rows:
            _cache_set(row)
            result[row.id] = row
    return result


async def get_by_fullname(
    db: AsyncSession,
    fullname: str,
) -> Optional[Comment]:
    row = (await db.execute(
        select(Comment).where(Comment.fullname == fullname).limit(1)
    )).scalar_one_or_none()
    if row is not None:
        _cache_set(row)
    return row


# ── Comment tree ─────────────────────────────────────────────────────────────

async def get_comment_tree(
    db: AsyncSession,
    link_id: int,
) -> list[Comment]:
    """Return all non-deleted comments for a link, ordered by date."""
    rows = (await db.execute(
        select(Comment)
        .where(Comment.link_id == link_id)
        .where(Comment.is_deleted == False)
        .order_by(Comment.date)
    )).scalars().all()
    return list(rows)


async def get_user_comments(
    db: AsyncSession,
    author_id: int,
    sort: str = 'new',
    time: str = 'all',
    limit: int = 25,
) -> list[Comment]:
    """Return comments by a user."""
    _time_filters = {
        'hour':  timedelta(hours=1),
        'day':   timedelta(days=1),
        'week':  timedelta(weeks=1),
        'month': timedelta(days=30),
        'year':  timedelta(days=365),
    }
    stmt = (
        select(Comment)
        .where(Comment.author_id == author_id)
        .where(Comment.is_deleted == False)
    )
    if time != 'all' and time in _time_filters:
        cutoff = datetime.utcnow() - _time_filters[time]
        stmt = stmt.where(Comment.date >= cutoff)

    if sort == 'new':
        stmt = stmt.order_by(Comment.date.desc())
    elif sort == 'top':
        stmt = stmt.order_by((Comment.ups - Comment.downs).desc())
    else:
        stmt = stmt.order_by(Comment.date.desc())

    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


# ── Votes ────────────────────────────────────────────────────────────────────

async def cast_vote(
    db: AsyncSession,
    account_id: int,
    comment_id: int,
    direction: int,
) -> None:
    """Cast or update a vote on a comment."""
    stmt = pg_insert(CommentVote).values(
        account_id=account_id,
        comment_id=comment_id,
        direction=direction,
    ).on_conflict_do_update(
        index_elements=['account_id', 'comment_id'],
        set_={'direction': direction, 'date': func.now()},
    )
    await db.execute(stmt)

    from sqlalchemy import case
    counts = (await db.execute(
        select(
            func.coalesce(func.sum(case((CommentVote.direction == 1, 1), else_=0)), 0).label('ups'),
            func.coalesce(func.sum(case((CommentVote.direction == -1, 1), else_=0)), 0).label('downs'),
        ).where(CommentVote.comment_id == comment_id)
    )).one()

    comment = await get_by_id(db, comment_id, use_cache=False)
    if comment:
        comment.ups = counts.ups
        comment.downs = counts.downs
        await db.flush()
        _cache_invalidate(comment)
        _cache_set(comment)


# ── Saves / inbox ────────────────────────────────────────────────────────────

async def save_comment(
    db: AsyncSession,
    account_id: int,
    comment_id: int,
    category: Optional[str] = None,
) -> None:
    await db.execute(
        pg_insert(CommentSave).values(
            account_id=account_id, comment_id=comment_id, category=category
        ).on_conflict_do_nothing()
    )


async def unsave_comment(
    db: AsyncSession,
    account_id: int,
    comment_id: int,
) -> None:
    await db.execute(
        delete(CommentSave)
        .where(CommentSave.account_id == account_id)
        .where(CommentSave.comment_id == comment_id)
    )


async def add_to_inbox(
    db: AsyncSession,
    account_id: int,
    comment_id: int,
    inbox_type: str = 'inbox',
) -> None:
    """Add a comment to an account's inbox (reply, selfreply, or mention)."""
    await db.execute(
        pg_insert(CommentInbox).values(
            account_id=account_id,
            comment_id=comment_id,
            type=inbox_type,
            is_read=False,
        ).on_conflict_do_nothing()
    )


async def mark_inbox_read(
    db: AsyncSession,
    account_id: int,
    comment_id: Optional[int] = None,
) -> None:
    """Mark inbox items as read. If comment_id is None, mark all."""
    from sqlalchemy import update
    stmt = (
        update(CommentInbox)
        .where(CommentInbox.account_id == account_id)
        .values(is_read=True)
    )
    if comment_id is not None:
        stmt = stmt.where(CommentInbox.comment_id == comment_id)
    await db.execute(stmt)


# ── Reports ──────────────────────────────────────────────────────────────────

async def report_comment(
    db: AsyncSession,
    account_id: int,
    comment_id: int,
    reason: Optional[str] = None,
) -> None:
    await db.execute(
        pg_insert(CommentReport).values(
            account_id=account_id, comment_id=comment_id, reason=reason
        ).on_conflict_do_nothing()
    )
    comment = await get_by_id(db, comment_id, use_cache=False)
    if comment:
        comment.reported += 1
        await db.flush()
        _cache_invalidate(comment)
        _cache_set(comment)


# ── Creation ─────────────────────────────────────────────────────────────────

async def create_comment(
    db: AsyncSession,
    author_id: int,
    link_id: int,
    body: str,
    parent_id: Optional[int] = None,
    ip: str = '',
    sendreplies: bool = True,
) -> Comment:
    from r2.lib.utils import to36
    comment = Comment(
        author_id=author_id,
        link_id=link_id,
        parent_id=parent_id,
        body=body,
        ip=ip,
        sendreplies=sendreplies,
        fullname='',
    )
    db.add(comment)
    await db.flush()
    comment.fullname = f't1_{to36(comment.id)}'

    # Increment num_comments on the parent link
    from r2.models.orm.link import Link as LinkModel
    from sqlalchemy import update
    await db.execute(
        update(LinkModel)
        .where(LinkModel.id == link_id)
        .values(num_comments=LinkModel.num_comments + 1)
    )

    await db.flush()
    _cache_set(comment)
    return comment


async def delete_comment(
    db: AsyncSession,
    comment: Comment,
) -> None:
    comment.is_deleted = True
    await db.flush()
    _cache_invalidate(comment)
