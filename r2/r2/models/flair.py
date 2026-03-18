# The contents of this file are subject to the Common Public Attribution
# License Version 1.0. (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
# http://code.reddit.com/LICENSE. The License is based on the Mozilla Public
# License Version 1.1, but Sections 14 and 15 have been added to cover use of
# software over a computer network and provide for limited attribution for the
# Original Developer. In addition, Exhibit A has been modified to be consistent
# with Exhibit B.
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License for
# the specific language governing rights and limitations under the License.
#
# The Original Code is reddit.
#
# The Original Developer is the Initial Developer.  The Initial Developer of
# the Original Code is reddit Inc.
#
# All portions of the code written by reddit are Copyright (c) 2006-2015 reddit
# Inc. All Rights Reserved.
###############################################################################
"""
Flair models — PostgreSQL-backed, fully async.

* FlairTemplate / FlairTemplateBySubredditIndex: link/user flair templates
  stored in the ``flair_templates`` table.
* UserFlair: per-(subreddit, user) flair stored in the ``user_flair`` table.

No legacy Thing/Relation/UserRel imports remain.
"""

from __future__ import annotations

from typing import List, Optional

from r2.lib.context import c
from r2.models.orm.flair import FlairTemplate as _ORMFlairTemplate
import r2.services.flair_templates as _svc
import r2.services.flair as _flair_svc


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_FLAIR = 'USER_FLAIR'
LINK_FLAIR = 'LINK_FLAIR'

MAX_FLAIR_TEMPLATES = _svc.MAX_FLAIR_TEMPLATES

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

NotFound = type('NotFound', (Exception,), {})


# ---------------------------------------------------------------------------
# Flair — per-(subreddit, user) flair assignment
# ---------------------------------------------------------------------------

class Flair:
    """Async proxy for a user_flair row."""

    def __init__(self, sr_id: int, account_id: int,
                 flair_text: Optional[str] = None,
                 flair_css_class: Optional[str] = None) -> None:
        self.sr_id = sr_id
        self.account_id = account_id
        self.flair_text = flair_text or ''
        self.flair_css_class = flair_css_class or ''

    @classmethod
    async def get(cls, sr_id: int, account_id: int) -> Optional['Flair']:
        """Return the Flair for *(sr_id, account_id)*, or None."""
        row = await _flair_svc.get_flair(c.db, sr_id=sr_id, account_id=account_id)
        if row is None:
            return None
        return cls(row.sr_id, row.account_id, row.flair_text, row.flair_css_class)

    @classmethod
    async def set(
        cls,
        sr_id: int,
        account_id: int,
        flair_text: Optional[str],
        flair_css_class: Optional[str],
    ) -> Optional['Flair']:
        """Upsert flair; returns None when both values are empty (row deleted)."""
        row = await _flair_svc.set_flair(
            c.db,
            sr_id=sr_id,
            account_id=account_id,
            flair_text=flair_text,
            flair_css_class=flair_css_class,
        )
        if row is None:
            return None
        return cls(row.sr_id, row.account_id, row.flair_text, row.flair_css_class)

    @classmethod
    async def for_subreddit(
        cls,
        sr_id: int,
        account_ids: Optional[List[int]] = None,
    ) -> List['Flair']:
        """Return all Flair rows for *sr_id*, optionally scoped to *account_ids*."""
        rows = await _flair_svc.get_flairs_for_sr(c.db, sr_id=sr_id, account_ids=account_ids)
        return [cls(r.sr_id, r.account_id, r.flair_text, r.flair_css_class) for r in rows]


# ---------------------------------------------------------------------------
# FlairTemplate wrapper
# ---------------------------------------------------------------------------

class FlairTemplate:
    """Thin wrapper around the ORM FlairTemplate row."""

    def __init__(self, orm_obj: Optional[_ORMFlairTemplate] = None) -> None:
        self._orm = orm_obj

    # -- ORM field pass-throughs ------------------------------------------

    @property
    def _id(self) -> Optional[str]:
        return self._orm.id if self._orm is not None else None

    @property
    def text(self) -> str:
        return self._orm.text if self._orm is not None else ''

    @text.setter
    def text(self, value: str) -> None:
        if self._orm is not None:
            self._orm.text = value or ''

    @property
    def css_class(self) -> str:
        return self._orm.css_class if self._orm is not None else ''

    @css_class.setter
    def css_class(self, value: str) -> None:
        if self._orm is not None:
            self._orm.css_class = value or ''

    @property
    def text_editable(self) -> bool:
        return self._orm.text_editable if self._orm is not None else False

    @text_editable.setter
    def text_editable(self, value: bool) -> None:
        if self._orm is not None:
            self._orm.text_editable = bool(value)

    # -- Persistence --------------------------------------------------------

    async def _commit(self) -> None:
        """Flush pending ORM changes to the database."""
        await c.db.flush()

    @classmethod
    async def _byID(cls, ft_id: str) -> 'FlairTemplate':
        """Fetch a FlairTemplate by its UUID primary key.

        Raises NotFound if the row does not exist.
        """
        orm = await _svc.get_by_id(c.db, ft_id)
        return cls(orm)

    # -- Business logic -----------------------------------------------------

    def covers(self, other_template) -> bool:
        """Return True if *other_template* is a subset of this template."""
        if isinstance(other_template, FlairTemplate):
            text_editable = other_template.text_editable
            text, css_class = other_template.text, other_template.css_class
        else:
            text_editable = False
            text, css_class = other_template

        if self.css_class != css_class:
            return False
        return self.text_editable or (not text_editable and self.text == text)

    # -- Factory ------------------------------------------------------------

    @classmethod
    async def _new(
        cls,
        text: str,
        css_class: str,
        text_editable: bool,
        sr_id: int,
        flair_type: str,
    ) -> 'FlairTemplate':
        """Create and persist a new FlairTemplate row."""
        orm = await _svc.create(
            c.db,
            sr_id=sr_id,
            text=text or '',
            css_class=css_class or '',
            text_editable=bool(text_editable),
            flair_type=flair_type,
        )
        return cls(orm)

    def __repr__(self) -> str:
        return f'<FlairTemplate id={self._id!r}>'


# ---------------------------------------------------------------------------
# FlairTemplateBySubredditIndex
# ---------------------------------------------------------------------------

class FlairTemplateBySubredditIndex:
    """Service-layer proxy for flair-template index operations."""

    @classmethod
    async def create_template(
        cls,
        sr_id: int,
        text: str = '',
        css_class: str = '',
        text_editable: bool = False,
        flair_type: str = USER_FLAIR,
    ) -> FlairTemplate:
        """Create a new flair template for *sr_id*.

        Raises OverflowError if MAX_FLAIR_TEMPLATES would be exceeded.
        """
        return await FlairTemplate._new(
            text=text,
            css_class=css_class,
            text_editable=text_editable,
            sr_id=sr_id,
            flair_type=flair_type,
        )

    @classmethod
    async def get_template_ids(
        cls,
        sr_id: int,
        flair_type: str = USER_FLAIR,
    ) -> List[str]:
        """Return ordered list of template IDs for *sr_id* / *flair_type*."""
        rows = await _svc.get_by_sr(c.db, sr_id=sr_id, flair_type=flair_type)
        return [r.id for r in rows]

    @classmethod
    async def get_template(
        cls,
        sr_id: int,
        ft_id: str,
        flair_type: Optional[str] = None,
    ) -> Optional[FlairTemplate]:
        """Fetch a template by ID, validating it belongs to *sr_id*.

        If *flair_type* is given only that type is searched.  Returns None
        when no matching template is found.
        """
        if flair_type:
            flair_types = [flair_type]
        else:
            flair_types = [USER_FLAIR, LINK_FLAIR]

        for ft in flair_types:
            ids = await cls.get_template_ids(sr_id, flair_type=ft)
            if ft_id in ids:
                try:
                    orm = await _svc.get_by_id(c.db, ft_id)
                    return FlairTemplate(orm)
                except _svc.NotFound:
                    return None
        return None

    @classmethod
    async def clear(
        cls,
        sr_id: int,
        flair_type: str = USER_FLAIR,
    ) -> None:
        """Delete all flair templates for *sr_id* / *flair_type*."""
        await _svc.clear(c.db, sr_id=sr_id, flair_type=flair_type)

    @classmethod
    async def delete_by_id(
        cls,
        sr_id: int,
        ft_id: str,
        flair_type: Optional[str] = None,
    ) -> bool:
        """Delete a single template by ID.

        Returns True if a row was deleted.
        """
        from r2.lib.app_globals import g

        if flair_type:
            flair_types = [flair_type]
        else:
            flair_types = [USER_FLAIR, LINK_FLAIR]

        for ft in flair_types:
            ids = await cls.get_template_ids(sr_id, flair_type=ft)
            if ft_id in ids:
                await _svc.delete(c.db, ft_id=ft_id)
                return True

        g.log.debug("couldn't find %s to delete", ft_id)
        return False

    @classmethod
    async def insert(
        cls,
        sr_id: int,
        ft_id: str,
        flair_type: str = USER_FLAIR,
        position: Optional[int] = None,
    ) -> None:
        """Move/insert *ft_id* to *position* within *sr_id* / *flair_type*."""
        await _svc.reorder(
            c.db,
            sr_id=sr_id,
            flair_type=flair_type,
            ft_ids=await cls._ids_after_insert(sr_id, ft_id, flair_type, position),
        )

    @classmethod
    async def _ids_after_insert(
        cls,
        sr_id: int,
        ft_id: str,
        flair_type: str,
        position: Optional[int],
    ) -> List[str]:
        ids = await cls.get_template_ids(sr_id, flair_type=flair_type)
        if ft_id in ids:
            ids.remove(ft_id)
        if position is None:
            position = len(ids)
        if position < 0 or position > len(ids):
            raise IndexError(position)
        ids.insert(position, ft_id)
        return ids
