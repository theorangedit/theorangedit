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
Award and Trophy model wrappers — replaces the legacy Thing/Relation
implementation with a PostgreSQL-backed implementation.

ORM models live in r2.models.orm.award.  All DB access goes through
r2.services.awards (r2/r2/services/awards.py).
"""

from __future__ import annotations

from typing import Optional

from r2.lib.app_globals import g
from r2.lib.context import c
from r2.lib.utils import to36
from r2.models.orm.award import Award as AwardORM, Trophy as TrophyORM
from r2.services import awards as _svc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Raised when an Award or Trophy lookup returns no result."""


# ---------------------------------------------------------------------------
# Award
# ---------------------------------------------------------------------------

class Award:
    """
    Thin wrapper around the ORM Award row.

    ORM fields:
        id          — Integer primary key
        codename    — String(100), unique
        title       — Text
        awardtype   — String(20), default 'regular'
        imgurl      — Text
        api_ok      — Boolean
        created     — DateTime(timezone=True)
    """

    def __init__(self, orm_row: AwardORM) -> None:
        self._orm = orm_row

    # -- Identity properties -------------------------------------------------

    @property
    def _id(self) -> int:
        return self._orm.id

    @property
    def _id36(self) -> str:
        return to36(self._orm.id)

    @property
    def _fullname(self) -> str:
        return f't6_{self._id36}'

    # -- Field properties ----------------------------------------------------

    @property
    def codename(self) -> str:
        return self._orm.codename

    @codename.setter
    def codename(self, value: str) -> None:
        self._orm.codename = value

    @property
    def title(self) -> str:
        return self._orm.title

    @title.setter
    def title(self, value: str) -> None:
        self._orm.title = value

    @property
    def awardtype(self) -> str:
        return self._orm.awardtype

    @awardtype.setter
    def awardtype(self, value: str) -> None:
        self._orm.awardtype = value

    @property
    def imgurl(self) -> str:
        return self._orm.imgurl

    @imgurl.setter
    def imgurl(self, value: str) -> None:
        self._orm.imgurl = value

    @property
    def api_ok(self) -> bool:
        return self._orm.api_ok

    @api_ok.setter
    def api_ok(self, value: bool) -> None:
        self._orm.api_ok = value

    # -- Persistence ---------------------------------------------------------

    async def _commit(self) -> None:
        """Flush pending ORM changes to the database."""
        await c.db.flush()

    # -- Classmethods --------------------------------------------------------

    @classmethod
    async def _byID(cls, award_id: int) -> 'Award':
        """Fetch an Award by integer primary key.  Raises NotFound if missing."""
        try:
            orm = await _svc.get_by_id(c.db, award_id)
        except _svc.NotFound:
            raise NotFound(f'Award id={award_id!r}')
        return cls(orm)

    @classmethod
    async def _by_fullname(cls, fullname: str) -> 'Award':
        """Fetch an Award by its fullname string (e.g. ``'t6_abc'``).

        Raises NotFound if the fullname is malformed or the award does not exist.
        """
        if not fullname.startswith('t6_'):
            raise NotFound(f'Invalid Award fullname: {fullname!r}')
        from r2.lib.utils import from36
        award_id = from36(fullname[3:])
        return await cls._byID(award_id)

    @classmethod
    async def _by_codename(cls, codename: str) -> 'Award':
        """Fetch an Award by codename (case-insensitive).  Raises NotFound if missing."""
        try:
            orm = await _svc.get_by_codename(c.db, codename)
        except _svc.NotFound:
            raise NotFound(f'Award codename={codename!r}')
        return cls(orm)

    @classmethod
    async def _all_awards(cls) -> list['Award']:
        """Return all awards ordered by id."""
        rows = await _svc.get_all(c.db)
        return [cls(r) for r in rows]

    @classmethod
    async def _new(
        cls,
        codename: str,
        title: str,
        awardtype: str,
        imgurl: str,
        api_ok: bool,
    ) -> 'Award':
        """Create a new Award and return it."""
        orm = await _svc.create(c.db, codename=codename, title=title,
                                awardtype=awardtype, imgurl=imgurl,
                                api_ok=api_ok)
        return cls(orm)

    @classmethod
    async def give_if_needed(
        cls,
        codename: str,
        user,
        description: Optional[str] = None,
        url: Optional[str] = None,
    ) -> Optional['Trophy']:
        """Give an award to a user, unless they already have it.

        Returns the Trophy.  Does nothing and returns None (with a debug log)
        if the award doesn't exist.
        """
        try:
            award = await cls._by_codename(codename)
        except NotFound:
            g.log.debug("No award named '%s'" % codename)
            return None

        trophies = await Trophy.by_account(user)

        for trophy in trophies:
            trophy_award = await trophy._thing2
            if trophy_award.codename == codename:
                g.log.debug("%s already has %s" % (user, codename))
                return trophy

        g.log.debug("Gave %s to %s" % (codename, user))
        return await Trophy._new(user, award, description=description, url=url)

    @classmethod
    async def take_away(cls, codename: str, user) -> None:
        """Remove all instances of an award from a user's trophy case.

        Logs silently if the award doesn't exist or the user doesn't have it.
        """
        found = False

        try:
            award = await cls._by_codename(codename)
        except NotFound:
            g.log.debug("No award named '%s'" % codename)
            return

        trophies = await Trophy.by_account(user)

        for trophy in trophies:
            trophy_award = await trophy._thing2
            if trophy_award.codename == codename:
                if found:
                    g.log.debug("%s had multiple %s awards!" % (user, codename))
                await trophy._delete()
                found = True

        if found:
            g.log.debug("Took %s from %s" % (codename, user))
        else:
            g.log.debug("%s didn't have %s" % (user, codename))

    def __repr__(self) -> str:
        return f'<Award id={self._orm.id} codename={self._orm.codename!r}>'


# ---------------------------------------------------------------------------
# Trophy
# ---------------------------------------------------------------------------

class Trophy:
    """
    Thin wrapper around the ORM Trophy row.

    ORM fields:
        id          — Integer primary key
        account_id  — BigInteger FK to accounts.id
        award_id    — Integer FK to awards.id
        description — Text (nullable)
        url         — Text (nullable)
        trophy_url  — Text (nullable, stored override)
        uid         — Text (nullable, for dedup)
        date        — DateTime(timezone=True)
    """

    def __init__(self, orm_row: TrophyORM) -> None:
        self._orm = orm_row
        # Lazy-loaded cache slots
        self._account_cache = None
        self._award_cache = None

    # -- Identity properties -------------------------------------------------

    @property
    def _id(self) -> int:
        return self._orm.id

    @property
    def _id36(self) -> str:
        return to36(self._orm.id)

    @property
    def _fullname(self) -> str:
        return f't6_{self._id36}'

    # -- Relation properties (async lazy load) --------------------------------

    @property
    async def _thing1(self):
        """The recipient Account — lazy-loaded."""
        if self._account_cache is None:
            from r2.models.account import Account
            self._account_cache = await Account._byID(self._orm.account_id)
        return self._account_cache

    @property
    async def _thing2(self) -> Award:
        """The Award — lazy-loaded."""
        if self._award_cache is None:
            self._award_cache = await Award._byID(self._orm.award_id)
        return self._award_cache

    # -- Field properties ----------------------------------------------------

    @property
    def description(self) -> Optional[str]:
        return self._orm.description

    @description.setter
    def description(self, value: Optional[str]) -> None:
        self._orm.description = value

    @property
    def url(self) -> Optional[str]:
        return self._orm.url

    @url.setter
    def url(self, value: Optional[str]) -> None:
        self._orm.url = value

    @property
    def date(self):
        return self._orm.date

    @property
    def trophy_url(self) -> Optional[str]:
        """Return the display URL for the trophy image.

        Prefers the stored ``url`` column; falls back to the award's ``imgurl``.
        This matches the original ``Trophy.trophy_url`` property logic.
        """
        if self._orm.url:
            return self._orm.url
        if self._award_cache is not None:
            return getattr(self._award_cache, 'imgurl', None)
        # If the award hasn't been loaded yet, return the stored trophy_url
        # column (which the service may have populated), or None.
        return self._orm.trophy_url

    # -- Persistence ---------------------------------------------------------

    async def _commit(self) -> None:
        """Flush pending ORM changes to the database."""
        await c.db.flush()

    async def _delete(self) -> None:
        """Delete this trophy from the database."""
        await _svc.delete_trophy(c.db, self._orm.id)

    # -- Classmethods --------------------------------------------------------

    @classmethod
    async def _byID(cls, trophy_id: int) -> 'Trophy':
        """Fetch a Trophy by integer primary key.  Raises NotFound if missing."""
        try:
            orm = await _svc.get_trophy(c.db, trophy_id)
        except _svc.NotFound:
            raise NotFound(f'Trophy id={trophy_id!r}')
        return cls(orm)

    @classmethod
    async def _new(
        cls,
        recipient,
        award: Award,
        description: Optional[str] = None,
        url: Optional[str] = None,
    ) -> 'Trophy':
        """Create a new Trophy and return it."""
        orm = await _svc.give_trophy(
            c.db,
            account_id=recipient._id,
            award_id=award._id,
            description=description,
            url=url,
        )
        t = cls(orm)
        # Pre-populate lazy-load caches so callers don't need a second await.
        t._account_cache = recipient
        t._award_cache = award
        return t

    @classmethod
    async def by_account(cls, account) -> list['Trophy']:
        """Return all trophies for an account, newest first."""
        rows = await _svc.get_trophies_by_account(c.db, account._id)
        return [cls(r) for r in rows]

    @classmethod
    async def by_award(cls, award: Award) -> list['Trophy']:
        """Return trophies for an award, newest first."""
        rows = await _svc.get_trophies_by_award(c.db, award._id)
        return [cls(r) for r in rows]

    @classmethod
    async def claim(
        cls,
        user,
        uid: str,
        award: Award,
        description: Optional[str],
        url: Optional[str],
    ) -> tuple['Trophy', bool]:
        """Claim a trophy using uid-based deduplication.

        Returns ``(trophy, preexisting)`` where ``preexisting`` is True if the
        trophy already existed for this (user, uid) pair.
        """
        try:
            orm = await _svc.get_trophy_by_uid(c.db, user._id, uid)
            trophy = cls(orm)
            return trophy, True
        except _svc.NotFound:
            pass

        orm = await _svc.give_trophy(
            c.db,
            account_id=user._id,
            award_id=award._id,
            description=description,
            url=url,
            uid=uid,
        )
        trophy = cls(orm)
        trophy._account_cache = user
        trophy._award_cache = award
        return trophy, False

    def __repr__(self) -> str:
        return (
            f'<Trophy id={self._orm.id} '
            f'account_id={self._orm.account_id} '
            f'award_id={self._orm.award_id}>'
        )


# ---------------------------------------------------------------------------
# FakeTrophy — pure Python, no DB, used for rendering
# ---------------------------------------------------------------------------

class FakeTrophy:
    def __init__(self, recipient, award, description=None, url=None):
        self._thing2 = award
        self._thing1 = recipient
        self.description = description
        self.url = url
        self.trophy_url = getattr(self, 'url',
                                  getattr(self._thing2, 'url', None))
        self._id = self._id36 = None
