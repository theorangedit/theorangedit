"""
ModAction model wrapper — replaces the old Cassandra UuidThing ModAction and
its associated View classes.

All mod action data lives in the `mod_actions` PostgreSQL table via the ORM
model at r2.models.orm.modaction.ModAction.  Cassandra View stubs are kept as
class names that raise NotImplementedError so that any stale import sites fail
loudly rather than silently.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from r2.lib.context import c
from r2.models.orm.modaction import ModAction as _OrmModAction
from r2.services.moderation import log_action as _svc_log, get_modlog as _svc_get


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Raised when a ModAction lookup returns no result."""


# ---------------------------------------------------------------------------
# ModAction wrapper
# ---------------------------------------------------------------------------

class ModAction:
    """
    Thin wrapper around the ORM ModAction row.

    ORM fields:
        id               — UUID primary key (string form, no dashes)
        sr_id            — BIGINT FK to subreddits.id
        mod_id           — BIGINT FK to accounts.id
        action           — VARCHAR(50) action name
        target_fullname  — VARCHAR(20), optional
        details          — TEXT, optional
        description      — TEXT, optional
        date             — TIMESTAMPTZ, server-set
    """

    def __init__(self, orm_row: _OrmModAction) -> None:
        self._orm = orm_row

    # -- ORM field pass-throughs -----------------------------------------

    @property
    def id(self) -> str:
        return self._orm.id

    @property
    def sr_id(self) -> int:
        return self._orm.sr_id

    @property
    def mod_id(self) -> int:
        return self._orm.mod_id

    @property
    def action(self) -> str:
        return self._orm.action

    @property
    def target_fullname(self) -> Optional[str]:
        return self._orm.target_fullname

    @property
    def details(self) -> Optional[str]:
        return self._orm.details

    @property
    def description(self) -> Optional[str]:
        return self._orm.description

    @property
    def date(self):
        return self._orm.date

    # -- Compatibility properties ----------------------------------------

    @property
    def _id(self) -> str:
        """String representation of the UUID primary key."""
        return str(self._orm.id)

    @property
    def _fullname(self) -> str:
        return f'ModAction_{self._orm.id}'

    # -- Persistence ---------------------------------------------------------

    @classmethod
    async def create(
        cls,
        sr,
        mod,
        action: str,
        target=None,
        details: Optional[str] = None,
        description: Optional[str] = None,
    ) -> 'ModAction':
        """Create and persist a new ModAction row.

        Parameters
        ----------
        sr      : subreddit object with an `.id` attribute
        mod     : account object with an `.id` attribute
        action  : action name string
        target  : optional object with a `._fullname` attribute
        details : optional subcategory string
        description : optional free-form string
        """
        target_fullname = getattr(target, '_fullname', None) if target else None
        orm = await _svc_log(
            c.db,
            sr_id=sr.id,
            mod_id=mod.id,
            action=action,
            target_fullname=target_fullname,
            details=details,
            description=description,
        )
        return cls(orm)

    @classmethod
    async def get_actions(
        cls,
        sr_id: int,
        mod_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 100,
        before=None,
    ) -> list['ModAction']:
        """Query mod actions with optional filters.

        Parameters
        ----------
        sr_id   : subreddit integer id
        mod_id  : filter to a specific moderator (optional)
        action  : filter to a specific action string (optional)
        limit   : maximum number of results
        before  : pagination cursor — a ModAction id string (optional, unused
                  in the current service implementation but accepted for
                  interface compatibility)
        """
        rows = await _svc_get(
            c.db,
            sr_id=sr_id,
            mod_id=mod_id,
            action=action,
            limit=limit,
        )
        return [cls(r) for r in rows]

    async def _commit(self) -> None:
        """Flush pending changes to the database."""
        await c.db.flush()

    def __repr__(self) -> str:
        return (
            f'<ModAction id={self._orm.id} action={self._orm.action!r}'
            f' sr_id={self._orm.sr_id}>'
        )


# ---------------------------------------------------------------------------
# Stub Cassandra View classes
# ---------------------------------------------------------------------------
# These names are preserved so that any remaining import sites produce a clear
# NotImplementedError rather than an ImportError.

class ModActionBySR:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class ModActionBySRMod:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class ModActionBySRAction:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")


class ModActionBySRActionMod:
    def __init__(self, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def add_object(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")

    @classmethod
    def query(cls, *a, **kw):
        raise NotImplementedError("Cassandra removed — use service layer")
