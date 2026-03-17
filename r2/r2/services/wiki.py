"""
Wiki service — replaces Cassandra WikiPage/WikiRevision/WikiPageEditors.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.wiki import WikiPage, WikiRevision


async def get_page(
    db: AsyncSession,
    sr_id: int,
    page_name: str,
) -> Optional[WikiPage]:
    return (await db.execute(
        select(WikiPage)
        .where(WikiPage.sr_id == sr_id)
        .where(WikiPage.page_name == page_name)
    )).scalar_one_or_none()


async def get_pages_for_sr(
    db: AsyncSession,
    sr_id: int,
    listed_only: bool = True,
) -> list[WikiPage]:
    stmt = select(WikiPage).where(WikiPage.sr_id == sr_id)
    if listed_only:
        stmt = stmt.where(WikiPage.listed == True)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def edit_page(
    db: AsyncSession,
    sr_id: int,
    page_name: str,
    author_id: int,
    content: str,
    reason: Optional[str] = None,
) -> WikiPage:
    """Create or update a wiki page, saving a revision."""
    # Save revision
    revision = WikiRevision(
        sr_id=sr_id,
        page_name=page_name,
        author_id=author_id,
        content=content,
        reason=reason,
    )
    db.add(revision)
    await db.flush()  # get revision.id

    # Upsert the page
    stmt = pg_insert(WikiPage).values(
        sr_id=sr_id,
        page_name=page_name,
        content=content,
        revision_id=revision.id,
        last_edit_by=author_id,
    ).on_conflict_do_update(
        index_elements=['sr_id', 'page_name'],
        set_={
            'content': content,
            'revision_id': revision.id,
            'last_edit_by': author_id,
            'last_edit_date': revision.date,
        }
    )
    await db.execute(stmt)
    await db.flush()

    return await get_page(db, sr_id, page_name)


async def get_revisions(
    db: AsyncSession,
    sr_id: int,
    page_name: str,
    limit: int = 25,
) -> list[WikiRevision]:
    rows = (await db.execute(
        select(WikiRevision)
        .where(WikiRevision.sr_id == sr_id)
        .where(WikiRevision.page_name == page_name)
        .where(WikiRevision.is_hidden == False)
        .order_by(WikiRevision.date.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def set_page_permlevel(
    db: AsyncSession,
    sr_id: int,
    page_name: str,
    permlevel: int,
) -> None:
    await db.execute(
        update(WikiPage)
        .where(WikiPage.sr_id == sr_id)
        .where(WikiPage.page_name == page_name)
        .values(permlevel=permlevel)
    )


async def hide_revision(
    db: AsyncSession,
    revision_id: str,
) -> None:
    await db.execute(
        update(WikiRevision)
        .where(WikiRevision.id == revision_id)
        .values(is_hidden=True)
    )
