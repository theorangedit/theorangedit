"""
Wiki model wrappers — replaces the old Cassandra-backed WikiPage, WikiRevision,
and associated View classes.

All wiki data lives in the `wiki_pages` and `wiki_revisions` PostgreSQL tables
via ORM models at r2.models.orm.wiki.  Cassandra View stubs are preserved as
class names that raise NotImplementedError so stale import sites fail loudly.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from r2.lib.context import c
from r2.models.orm.wiki import WikiPage as _OrmWikiPage, WikiRevision as _OrmWikiRevision
from r2.services.wiki import (
    get_page as _svc_get_page,
    get_pages_for_sr as _svc_get_pages,
    edit_page as _svc_edit_page,
    get_revisions as _svc_get_revisions,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Raised when a wiki page or revision lookup returns no result."""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def wiki_id(sr_id36: str, page_name: str) -> str:
    """Return the canonical identifier string for a wiki page.

    Matches the old wiki_id() convention used throughout the codebase.
    """
    return f'{sr_id36}/{page_name}'


# ---------------------------------------------------------------------------
# WikiPage wrapper
# ---------------------------------------------------------------------------

class WikiPage:
    """
    Thin wrapper around the ORM WikiPage row.

    ORM fields (composite PK: sr_id + page_name):
        sr_id          — BIGINT FK to subreddits.id
        page_name      — TEXT
        content        — TEXT
        revision_id    — UUID of the most recent WikiRevision (nullable)
        last_edit_by   — BIGINT FK to accounts.id (nullable)
        last_edit_date — TIMESTAMPTZ (nullable)
        permlevel      — SMALLINT  0=public 1=wiki-editors only 2=mods only
        listed         — BOOLEAN
    """

    def __init__(self, orm_row: _OrmWikiPage) -> None:
        self._orm = orm_row

    # -- ORM field pass-throughs -----------------------------------------

    @property
    def sr_id(self) -> int:
        return self._orm.sr_id

    @property
    def page_name(self) -> str:
        return self._orm.page_name

    @property
    def content(self) -> str:
        return self._orm.content or ''

    @property
    def revision_id(self) -> Optional[str]:
        return self._orm.revision_id

    @property
    def last_edit_by(self) -> Optional[int]:
        return self._orm.last_edit_by

    @property
    def last_edit_date(self):
        return self._orm.last_edit_date

    @property
    def permlevel(self) -> int:
        return self._orm.permlevel

    @property
    def listed(self) -> bool:
        return self._orm.listed

    # -- Compatibility properties ----------------------------------------

    @property
    def _id(self) -> str:
        return f'{self._orm.sr_id}_{self._orm.page_name}'

    @property
    def may_revise(self) -> bool:
        """Always True — permission checks are handled by the controller layer."""
        return True

    # -- Persistence ---------------------------------------------------------

    @classmethod
    async def get(cls, sr, page_name: str) -> 'WikiPage':
        """Fetch a page by subreddit object and page name.

        Raises NotFound if the page does not exist.
        """
        orm = await _svc_get_page(c.db, sr_id=sr.id, page_name=page_name)
        if orm is None:
            raise NotFound(page_name)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        sr,
        page_name: str,
        author,
        content: str = '',
    ) -> 'WikiPage':
        """Create a new wiki page (or update it if it already exists).

        Parameters
        ----------
        sr        : subreddit object with an `.id` attribute
        page_name : page name string
        author    : account object with an `.id` attribute
        content   : initial markdown content
        """
        orm = await _svc_edit_page(
            c.db,
            sr_id=sr.id,
            page_name=page_name,
            author_id=author.id,
            content=content,
            reason='page created',
        )
        return cls(orm)

    async def revise(
        self,
        content: str,
        author,
        reason: str = '',
        db=None,
    ) -> 'WikiRevision':
        """Save a new revision of this page.

        Parameters
        ----------
        content : new markdown content
        author  : account object with an `.id` attribute
        reason  : optional edit summary
        db      : ignored — uses c.db from context (kept for compat)
        """
        updated_orm = await _svc_edit_page(
            c.db,
            sr_id=self._orm.sr_id,
            page_name=self._orm.page_name,
            author_id=author.id,
            content=content,
            reason=reason or None,
        )
        # Refresh our internal ORM reference so .content etc reflect the edit.
        self._orm = updated_orm._orm if isinstance(updated_orm, WikiPage) else updated_orm

        # Return the most recent WikiRevision for this page.
        revisions = await WikiRevision.get_listing(
            self._orm.sr_id, self._orm.page_name, limit=1
        )
        return revisions[0] if revisions else None

    async def _commit(self) -> None:
        """Flush pending changes to the database."""
        await c.db.flush()

    @classmethod
    async def get_listing(cls, sr_id: int) -> list['WikiPage']:
        """Return all listed pages for a subreddit."""
        rows = await _svc_get_pages(c.db, sr_id=sr_id, listed_only=True)
        return [cls(r) for r in rows]

    def __repr__(self) -> str:
        return f'<WikiPage sr_id={self._orm.sr_id} page={self._orm.page_name!r}>'


# ---------------------------------------------------------------------------
# WikiRevision wrapper
# ---------------------------------------------------------------------------

class WikiRevision:
    """
    Thin wrapper around the ORM WikiRevision row.

    ORM fields:
        id        — UUID primary key (string, no dashes)
        sr_id     — BIGINT FK to subreddits.id
        page_name — TEXT
        author_id — BIGINT FK to accounts.id (nullable)
        content   — TEXT
        reason    — TEXT (nullable)
        date      — TIMESTAMPTZ
        is_hidden — BOOLEAN
    """

    def __init__(self, orm_row: _OrmWikiRevision) -> None:
        self._orm = orm_row

    # -- ORM field pass-throughs -----------------------------------------

    @property
    def id(self) -> str:
        return self._orm.id

    @property
    def sr_id(self) -> int:
        return self._orm.sr_id

    @property
    def page_name(self) -> str:
        return self._orm.page_name

    @property
    def author_id(self) -> Optional[int]:
        return self._orm.author_id

    @property
    def content(self) -> str:
        return self._orm.content or ''

    @property
    def reason(self) -> Optional[str]:
        return self._orm.reason

    @property
    def date(self):
        return self._orm.date

    @property
    def is_hidden(self) -> bool:
        return self._orm.is_hidden

    # -- Compatibility properties ----------------------------------------

    @property
    def _id(self) -> str:
        """String representation of the UUID primary key."""
        return str(self._orm.id)

    # -- Persistence ---------------------------------------------------------

    @classmethod
    async def _byID(cls, revision_id: str) -> 'WikiRevision':
        """Fetch a single revision by its UUID string.  Raises NotFound if missing."""
        from sqlalchemy import select as _select
        orm = (await c.db.execute(
            _select(_OrmWikiRevision).where(_OrmWikiRevision.id == revision_id)
        )).scalar_one_or_none()
        if orm is None:
            raise NotFound(revision_id)
        return cls(orm)

    @classmethod
    async def get_listing(
        cls,
        sr_id: int,
        page_name: str,
        limit: int = 100,
    ) -> list['WikiRevision']:
        """Return revision history for a page, newest first."""
        rows = await _svc_get_revisions(
            c.db, sr_id=sr_id, page_name=page_name, limit=limit
        )
        return [cls(r) for r in rows]

    def __repr__(self) -> str:
        return f'<WikiRevision id={self._orm.id} page={self._orm.page_name!r}>'


# ---------------------------------------------------------------------------
# Stub Cassandra View classes
# ---------------------------------------------------------------------------
# These names are preserved so that any remaining import sites produce a clear
# NotImplementedError rather than an ImportError.

class WikiPageEditors:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def _set_values(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def _remove(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def _byID(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class WikiRevisionHistoryByPage:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class WikiPagesBySR:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class WikiRevisionsRecentBySR:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class ImagesByWikiPage:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_image(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def get_images(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def get_image_count(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def delete_image(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")
