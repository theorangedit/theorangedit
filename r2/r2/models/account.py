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
r2.models.account
~~~~~~~~~~~~~~~~~

Public API for Account objects.  The ORM model lives in
r2.models.orm.account; this module monkey-patches legacy compat shims onto it
so that all existing callers (controllers, templates, scripts) continue to
work without modification.

Python 3 / FastAPI / SQLAlchemy 2.x async rewrite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from r2.models.orm.account import Account as _AccountORM, AccountKarma
from r2.services import accounts as account_svc
from r2.lib.context import c
from r2.lib.app_globals import g
from r2.lib.utils import to36, from36


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AccountExists(Exception):
    """Raised when attempting to register a name that is already taken."""
    pass


class NotFound(Exception):
    """Raised when a requested object does not exist.

    Re-exported here for backwards compatibility with callers that do:
        from r2.models.account import NotFound
    """
    pass


# ---------------------------------------------------------------------------
# Compat classmethods – added to the ORM Account class
# ---------------------------------------------------------------------------

@classmethod
async def _byID(
    cls,
    id_or_ids,
    data: bool = True,
    return_dict: bool = False,
    stale: bool = False,
):
    """Look up Account(s) by integer primary key.

    - Single int  → returns a single Account (raises NotFound if missing and
                    return_dict is False).
    - list/set/dict_keys → returns dict {id: Account} by default; if
                           return_dict=False returns a list in unspecified order.
    """
    db = c.db
    if isinstance(id_or_ids, (list, set, type({}.keys()))):
        ids = list(id_or_ids)
        result_dict = await account_svc.get_by_ids(db, ids)
        if return_dict:
            return result_dict
        return list(result_dict.values())

    # Single lookup
    account = await account_svc.get_by_id(db, int(id_or_ids))
    if account is None:
        raise NotFound(f'Account {id_or_ids!r}')
    return account


@classmethod
async def _by_name(cls, name: str, allow_deleted: bool = False):
    """Look up an Account by username (case-insensitive).

    Raises NotFound if no matching account exists.
    """
    db = c.db
    account = await account_svc.get_by_name(db, name, allow_deleted=allow_deleted)
    if account is None:
        raise NotFound(f'Account {name!r}')
    return account


@classmethod
async def _byID36(cls, id36: str, data: bool = True):
    """Look up an Account by its base-36-encoded ID string."""
    account_id = from36(id36)
    return await cls._byID(account_id, data=data)


@classmethod
async def _by_fullname(cls, fullname: str):
    """Look up an Account by its fullname string (e.g. ``'t2_abc'``).

    Raises NotFound if the fullname is malformed or the account does not exist.
    """
    if not fullname.startswith('t2_'):
        raise NotFound(f'Invalid Account fullname: {fullname!r}')
    id36 = fullname[3:]
    return await cls._byID36(id36)


async def _commit(self):
    """Persist in-memory changes to the database and invalidate caches."""
    db = c.db
    await db.flush()
    account_svc._cache_invalidate(self)
    account_svc._cache_set(self)


# ---------------------------------------------------------------------------
# Properties – shims over the new ORM attribute names
# ---------------------------------------------------------------------------

def _prop_id(self) -> int:
    return self.id

def _prop_fullname(self) -> str:
    return f't2_{to36(self.id)}'

def _prop_deleted(self) -> bool:
    return self.is_deleted

def _prop_spam(self) -> bool:
    return self.is_spam

def _prop_id36(self) -> str:
    return to36(self.id)

def _prop_date(self) -> datetime:
    return self.date

def _prop_age(self):
    """Return a timedelta representing the account's age."""
    d = self.date
    naive = d.replace(tzinfo=None) if d.tzinfo is not None else d
    return datetime.utcnow() - naive

def _prop_link_karma(self) -> int:
    """Return total link karma, using g.thingcache when available."""
    if g.thingcache:
        cached = g.thingcache.get(f'lkarma:{self.id}')
        if cached is not None:
            return cached
    # Fall back to summing loaded karma rows (only works if relationship
    # was eagerly loaded; otherwise callers should use the service layer).
    try:
        return sum(k.link_karma for k in self.karma)
    except Exception:
        return 0

def _prop_comment_karma(self) -> int:
    """Return total comment karma, using g.thingcache when available."""
    if g.thingcache:
        cached = g.thingcache.get(f'ckarma:{self.id}')
        if cached is not None:
            return cached
    try:
        return sum(k.comment_karma for k in self.karma)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Instance methods
# ---------------------------------------------------------------------------

def make_cookie(self, timestr: Optional[str] = None) -> str:
    """Return the session cookie string for this account."""
    return account_svc.make_cookie(self, timestr)


def verify_password(self, password: str) -> bool:
    """Return True if *password* matches this account's stored hash."""
    return account_svc.verify_password(password, self.password)


async def incr_karma(self, kind: str, sr, amt: int) -> None:
    """Atomically increment link or comment karma for this account in *sr*."""
    db = c.db
    if self.disable_karma:
        return
    await account_svc.increment_karma(
        db,
        self.id,
        sr.id,
        link_delta=amt if kind == 'link' else 0,
        comment_delta=amt if kind == 'comment' else 0,
    )


# ---------------------------------------------------------------------------
# Patch all compat members onto the ORM class
# ---------------------------------------------------------------------------

_AccountORM._byID = _byID
_AccountORM._by_name = _by_name
_AccountORM._byID36 = _byID36
_AccountORM._by_fullname = _by_fullname
_AccountORM._commit = _commit

_AccountORM._id = property(_prop_id)
# Note: the ORM model already defines fullname as a property returning
# 't2_{self.id}'.  We add _fullname as a separate compat shim.
_AccountORM._fullname = property(_prop_fullname)
_AccountORM._deleted = property(_prop_deleted)
_AccountORM._spam = property(_prop_spam)
_AccountORM._id36 = property(_prop_id36)
_AccountORM._date = property(_prop_date)
_AccountORM._age = property(_prop_age)
_AccountORM.link_karma = property(_prop_link_karma)
_AccountORM.comment_karma = property(_prop_comment_karma)

_AccountORM.make_cookie = make_cookie
_AccountORM.verify_password = verify_password
_AccountORM.incr_karma = incr_karma

# Public name – everything in the codebase imports `Account` from here.
Account = _AccountORM


# ---------------------------------------------------------------------------
# Stub / compat classes
# ---------------------------------------------------------------------------

class FakeAccount(Account):
    """A non-persistent account object used for anonymous users etc."""
    _nodb = True
    pref_no_profanity = True

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return not self.__eq__(other)


class DeletedUser(FakeAccount):
    """Represents the tombstone shown where a deleted user once was."""

    @property
    def name(self) -> str:
        return '[deleted]'

    @property
    def _deleted(self) -> bool:  # type: ignore[override]
        return True

    @property
    def _fullname(self):  # type: ignore[override]
        raise NotImplementedError('DeletedUser has no fullname')

    @property
    def _id(self):  # type: ignore[override]
        raise NotImplementedError('DeletedUser has no id')

    def __setattr__(self, attr, val):
        if attr == '_deleted':
            return
        object.__setattr__(self, attr, val)


class Friend:
    """Stub for the legacy Friend Relation class.  No-op in the new stack."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'Friend relations are not implemented in the async ORM layer. '
            'Use a service function instead.'
        )


class BlockedSubredditsByAccount:
    """Legacy Cassandra DenormalizedRelation — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'BlockedSubredditsByAccount (Cassandra) has been removed. '
            'Use the subreddits service instead.'
        )

    @classmethod
    def block(cls, user, sr):
        raise NotImplementedError

    @classmethod
    def unblock(cls, user, sr):
        raise NotImplementedError

    @classmethod
    def is_blocked(cls, user, sr):
        raise NotImplementedError


class AccountsByCanonicalEmail:
    """Legacy Cassandra View — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'AccountsByCanonicalEmail (Cassandra) has been removed.'
        )

    @classmethod
    def update_email(cls, account, old, new):
        raise NotImplementedError

    @classmethod
    def get_accounts(cls, email_address):
        raise NotImplementedError


class SubredditParticipationByAccount:
    """Legacy Cassandra DenormalizedRelation — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'SubredditParticipationByAccount (Cassandra) has been removed.'
        )

    @classmethod
    def mark_participated(cls, account, subreddit):
        raise NotImplementedError


class QuarantinedSubredditOptInsByAccount:
    """Legacy Cassandra DenormalizedRelation — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'QuarantinedSubredditOptInsByAccount (Cassandra) has been removed.'
        )

    @classmethod
    def opt_in(cls, account, subreddit):
        raise NotImplementedError

    @classmethod
    def opt_out(cls, account, subreddit):
        raise NotImplementedError

    @classmethod
    def is_opted_in(cls, user, subreddit):
        raise NotImplementedError


# Re-export AccountKarma so callers that do
#   from r2.models.account import AccountKarma
# continue to work.
__all__ = [
    'Account',
    'AccountExists',
    'AccountKarma',
    'BlockedSubredditsByAccount',
    'AccountsByCanonicalEmail',
    'DeletedUser',
    'FakeAccount',
    'Friend',
    'NotFound',
    'QuarantinedSubredditOptInsByAccount',
    'SubredditParticipationByAccount',
]
