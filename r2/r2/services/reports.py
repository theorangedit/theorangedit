"""
r2.services.reports
~~~~~~~~~~~~~~~~~~~

Async service layer for the report system.

Each content type has its own table (link_reports, comment_reports,
subreddit_reports, message_reports).  The ``state`` column encodes:
  -1 = rejected (report was wrong / item approved)
   0 = pending  (unactioned)
   1 = accepted (item was removed/banned)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.relations import (
    LinkReport,
    CommentReport,
    SubredditReport,
    MessageReport,
)

STATE_PENDING = 0
STATE_ACCEPTED = 1
STATE_REJECTED = -1


# ---------------------------------------------------------------------------
# Lightweight proxy used by queries.new_report / queries.clear_reports
# ---------------------------------------------------------------------------

class ReportProxy:
    """Mimics the legacy Relation object shape expected by queries.py."""

    def __init__(self, account_id: int, thing_id: int, reason: Optional[str],
                 date: datetime) -> None:
        self._thing1_id = account_id
        self._thing2_id = thing_id
        self.reason = reason
        self._date = date
        self._name = '0'  # pending


# ---------------------------------------------------------------------------
# Dispatch helpers
# ---------------------------------------------------------------------------

def _table_for(thing):
    from r2.models.orm.link import Link
    from r2.models.orm.comment import Comment
    from r2.models.orm.message import Message
    from r2.models.orm.subreddit import Subreddit

    if isinstance(thing, Link):
        return LinkReport, 'link_id', thing.id
    elif isinstance(thing, Comment):
        return CommentReport, 'comment_id', thing.id
    elif isinstance(thing, Message):
        return MessageReport, 'message_id', thing.id
    elif isinstance(thing, Subreddit):
        return SubredditReport, 'sr_id', thing.id
    raise TypeError(f"No report table for {type(thing)!r}")


def _thing_id_col(table_cls):
    cols = {
        LinkReport: LinkReport.link_id,
        CommentReport: CommentReport.comment_id,
        SubredditReport: SubredditReport.sr_id,
        MessageReport: MessageReport.message_id,
    }
    return cols[table_cls]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def new_report(
    db: AsyncSession,
    account_id: int,
    thing,
    reason: Optional[str] = None,
) -> Optional[ReportProxy]:
    """Insert a report row if one doesn't already exist.

    Returns a ReportProxy on success, None if already reported by this user.
    """
    table_cls, fk_col_name, thing_id = _table_for(thing)

    # Check for duplicate
    thing_id_col = _thing_id_col(table_cls)
    existing = await db.execute(
        select(table_cls).where(
            table_cls.account_id == account_id,
            thing_id_col == thing_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return None

    stmt = (
        pg_insert(table_cls)
        .values(account_id=account_id, **{fk_col_name: thing_id}, reason=reason, state=STATE_PENDING)
        .on_conflict_do_nothing()
        .returning(table_cls)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return ReportProxy(row.account_id, thing_id, row.reason, row.date)


async def get_reports_for_thing(
    db: AsyncSession,
    thing,
) -> list[ReportProxy]:
    """Return all report rows for *thing* as ReportProxy objects."""
    table_cls, fk_col_name, thing_id = _table_for(thing)
    thing_id_col = _thing_id_col(table_cls)

    result = await db.execute(
        select(table_cls).where(thing_id_col == thing_id)
    )
    rows = result.scalars().all()
    return [ReportProxy(r.account_id, thing_id, r.reason, r.date) for r in rows]


async def accept_reports(
    db: AsyncSession,
    things: Sequence,
    correct: bool = True,
) -> None:
    """Set state on all pending reports for *things* and zero their reported counter."""
    new_state = STATE_ACCEPTED if correct else STATE_REJECTED

    for thing in things:
        table_cls, fk_col_name, thing_id = _table_for(thing)
        thing_id_col = _thing_id_col(table_cls)

        await db.execute(
            update(table_cls)
            .where(thing_id_col == thing_id, table_cls.state == STATE_PENDING)
            .values(state=new_state)
        )

        # Zero the reported counter on the thing itself
        thing.reported = 0


async def get_user_reports(
    db: AsyncSession,
    account_id: int,
    thing_cls,
) -> list[ReportProxy]:
    """Return all reports made by *account_id* for a given thing class."""
    from r2.models.orm.link import Link
    from r2.models.orm.comment import Comment
    from r2.models.orm.message import Message
    from r2.models.orm.subreddit import Subreddit

    cls_map = {
        Link: (LinkReport, LinkReport.link_id),
        Comment: (CommentReport, CommentReport.comment_id),
        Message: (MessageReport, MessageReport.message_id),
        Subreddit: (SubredditReport, SubredditReport.sr_id),
    }
    if thing_cls not in cls_map:
        return []
    table_cls, thing_id_col = cls_map[thing_cls]

    result = await db.execute(
        select(table_cls).where(table_cls.account_id == account_id)
    )
    rows = result.scalars().all()
    return [ReportProxy(r.account_id, int(thing_id_col.__get__(r, type(r))), r.reason, r.date) for r in rows]
