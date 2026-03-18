"""
Flair template service — replaces Cassandra FlairTemplate/FlairTemplateBySubredditIndex.
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from r2.models.orm.flair import FlairTemplate


MAX_FLAIR_TEMPLATES = 350


class NotFound(Exception):
    pass


# ── Retrieval ─────────────────────────────────────────────────────────────────

async def get_by_id(db: AsyncSession, ft_id: str) -> FlairTemplate:
    """Return a FlairTemplate by primary key. Raises NotFound if absent."""
    row = await db.get(FlairTemplate, ft_id)
    if row is None:
        raise NotFound(f'FlairTemplate {ft_id!r} not found')
    return row


async def get_by_sr(
    db: AsyncSession,
    sr_id: int,
    flair_type: str,
) -> list[FlairTemplate]:
    """Return all flair templates for a subreddit/type, ordered by position."""
    rows = (await db.execute(
        select(FlairTemplate)
        .where(FlairTemplate.sr_id == sr_id)
        .where(FlairTemplate.flair_type == flair_type)
        .order_by(FlairTemplate.position)
    )).scalars().all()
    return list(rows)


# ── Mutation ──────────────────────────────────────────────────────────────────

async def create(
    db: AsyncSession,
    sr_id: int,
    text: str,
    css_class: str,
    text_editable: bool,
    flair_type: str,
) -> FlairTemplate:
    """Create a new flair template appended at the end of the list.

    Raises OverflowError if the subreddit already has MAX_FLAIR_TEMPLATES
    templates of this type.
    """
    count_result = await db.execute(
        select(func.count())
        .select_from(FlairTemplate)
        .where(FlairTemplate.sr_id == sr_id)
        .where(FlairTemplate.flair_type == flair_type)
    )
    current_count = count_result.scalar()
    if current_count >= MAX_FLAIR_TEMPLATES:
        raise OverflowError(
            f'Subreddit {sr_id} already has {MAX_FLAIR_TEMPLATES} '
            f'{flair_type} templates'
        )

    ft = FlairTemplate(
        sr_id=sr_id,
        flair_type=flair_type,
        position=current_count,
        text=text,
        css_class=css_class,
        text_editable=text_editable,
    )
    db.add(ft)
    await db.flush()
    return ft


async def update(  # noqa: A001
    db: AsyncSession,
    ft_id: str,
    text: str,
    css_class: str,
    text_editable: bool,
) -> FlairTemplate:
    """Update text/css_class/text_editable on an existing template."""
    await db.execute(
        update(FlairTemplate)
        .where(FlairTemplate.id == ft_id)
        .values(text=text, css_class=css_class, text_editable=text_editable)
    )
    return await get_by_id(db, ft_id)


async def delete(db: AsyncSession, ft_id: str) -> None:
    """Delete a flair template and close the gap in position ordering."""
    ft = await get_by_id(db, ft_id)
    sr_id = ft.sr_id
    flair_type = ft.flair_type
    removed_pos = ft.position

    await db.execute(sa_delete(FlairTemplate).where(FlairTemplate.id == ft_id))

    # Shift positions down for all templates that followed the deleted one
    await db.execute(
        update(FlairTemplate)
        .where(FlairTemplate.sr_id == sr_id)
        .where(FlairTemplate.flair_type == flair_type)
        .where(FlairTemplate.position > removed_pos)
        .values(position=FlairTemplate.position - 1)
    )
    await db.flush()


async def clear(db: AsyncSession, sr_id: int, flair_type: str) -> None:
    """Delete all flair templates of a given type for a subreddit."""
    await db.execute(
        sa_delete(FlairTemplate)
        .where(FlairTemplate.sr_id == sr_id)
        .where(FlairTemplate.flair_type == flair_type)
    )
    await db.flush()


async def reorder(
    db: AsyncSession,
    sr_id: int,
    flair_type: str,
    ft_ids: list[str],
) -> None:
    """Reorder flair templates by assigning positions matching the supplied id list.

    ft_ids must contain exactly the same IDs currently stored for this
    sr_id/flair_type; any mismatch is silently ignored (extra ids are skipped,
    missing ids are left at their existing position).
    """
    for new_pos, ft_id in enumerate(ft_ids):
        await db.execute(
            update(FlairTemplate)
            .where(FlairTemplate.id == ft_id)
            .where(FlairTemplate.sr_id == sr_id)
            .where(FlairTemplate.flair_type == flair_type)
            .values(position=new_pos)
        )
    await db.flush()
