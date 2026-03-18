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
r2.models.link
~~~~~~~~~~~~~~

Public API for Link, Comment, and Message objects.

The ORM models live in r2.models.orm.{link,comment,message}; this module
monkey-patches legacy compat shims onto each of them so that all existing
callers (controllers, templates, scripts) continue to work without modification.

Python 3 / FastAPI / SQLAlchemy 2.x async rewrite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from r2.models.orm.link import Link as _LinkORM
from r2.models.orm.comment import Comment as _CommentORM
from r2.models.orm.message import Message as _MessageORM
from r2.services import links as link_svc
from r2.services import comments as comment_svc
from r2.services import messages as message_svc
from r2.lib.context import c
from r2.lib.utils import to36, from36


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Raised when a requested object does not exist.

    Re-exported here for backwards compatibility with callers that do:
        from r2.models.link import NotFound
    """
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_multi(id_or_ids) -> bool:
    """Return True if *id_or_ids* represents a collection rather than a scalar."""
    return isinstance(id_or_ids, (list, set, type({}.keys())))


def _naive(dt: datetime) -> datetime:
    """Strip timezone info from *dt* for arithmetic with utcnow()."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


# ===========================================================================
# Link
# ===========================================================================

# -- classmethods ------------------------------------------------------------

@classmethod
async def _link_byID(
    cls,
    id_or_ids,
    data: bool = True,
    return_dict: bool = False,
    stale: bool = False,
):
    """Look up Link(s) by integer primary key.

    Single int  -> returns a single Link (raises NotFound if missing).
    collection  -> returns dict {id: Link}; if return_dict=False, a list.
    """
    db = c.db
    if _is_multi(id_or_ids):
        ids = list(id_or_ids)
        result = await link_svc.get_by_ids(db, ids)
        if return_dict:
            return result
        return list(result.values())

    link = await link_svc.get_by_id(db, int(id_or_ids))
    if link is None:
        raise NotFound(f'Link {id_or_ids!r}')
    return link


@classmethod
async def _link_by_fullname(
    cls,
    fullname_or_names,
    data: bool = True,
    return_dict: bool = False,
):
    """Look up Link(s) by fullname string(s) (e.g. ``'t3_abc'``).

    Single str  -> returns a single Link (raises NotFound if missing).
    collection  -> returns dict {fullname: Link}; if return_dict=False, a list.
    """
    db = c.db
    if _is_multi(fullname_or_names):
        names = list(fullname_or_names)
        result = {}
        for fn in names:
            link = await link_svc.get_by_fullname(db, fn)
            if link is not None:
                result[fn] = link
        if return_dict:
            return result
        return list(result.values())

    link = await link_svc.get_by_fullname(db, fullname_or_names)
    if link is None:
        raise NotFound(f'Link {fullname_or_names!r}')
    return link


@classmethod
async def _link_by_url(cls, url: str, sr=None):
    """Return a list of non-deleted Links matching *url*, optionally scoped to *sr*."""
    db = c.db
    sr_id = sr.id if sr is not None else None
    return await link_svc.get_by_url(db, url, sr_id=sr_id)


async def _link_commit(self):
    """Persist in-memory changes and invalidate caches."""
    db = c.db
    await db.flush()
    link_svc._cache_invalidate(self)
    link_svc._cache_set(self)


async def _link_set_flair(self, text: Optional[str], css_class: Optional[str], **_kwargs) -> None:
    """Write flair directly onto the link's own columns and persist."""
    self.flair_text = text or None
    self.flair_css_class = css_class or None
    await self._commit()


# -- property shims ----------------------------------------------------------

def _link_prop_id(self) -> int:
    return self.id

# _fullname is already stored as a column on the ORM model; provide a shim
# for callers that access the legacy underscore-prefixed attribute.
def _link_prop_fullname_shim(self) -> str:
    return self.fullname

def _link_prop_deleted(self) -> bool:
    return self.is_deleted

def _link_prop_spam(self) -> bool:
    return self.is_spam

def _link_prop_id36(self) -> str:
    return to36(self.id)

def _link_prop_date(self) -> datetime:
    return self.date

def _link_prop_age(self):
    return datetime.utcnow() - _naive(self.date)

def _link_prop_author_slow(self):
    raise NotImplementedError(
        'Link.author_slow is not available in the async ORM layer. '
        'Use await accounts.get_by_id(c.db, link.author_id) instead.'
    )

def _link_prop_subreddit_slow(self):
    raise NotImplementedError(
        'Link.subreddit_slow is not available in the async ORM layer. '
        'Use await subreddits.get_by_id(c.db, link.sr_id) instead.'
    )


# -- patch -------------------------------------------------------------------

_LinkORM._byID = _link_byID
_LinkORM._by_fullname = _link_by_fullname
_LinkORM._by_url = _link_by_url
_LinkORM._commit = _link_commit
_LinkORM.set_flair = _link_set_flair

_LinkORM._id = property(_link_prop_id)
_LinkORM._fullname = property(_link_prop_fullname_shim)
_LinkORM._deleted = property(_link_prop_deleted)
_LinkORM._spam = property(_link_prop_spam)
_LinkORM._id36 = property(_link_prop_id36)
_LinkORM._date = property(_link_prop_date)
_LinkORM._age = property(_link_prop_age)
_LinkORM.author_slow = property(_link_prop_author_slow)
_LinkORM.subreddit_slow = property(_link_prop_subreddit_slow)

# Public name
Link = _LinkORM


# ===========================================================================
# Comment
# ===========================================================================

# -- classmethods ------------------------------------------------------------

@classmethod
async def _comment_byID(
    cls,
    id_or_ids,
    data: bool = True,
    return_dict: bool = False,
    stale: bool = False,
):
    """Look up Comment(s) by integer primary key.

    Single int  -> returns a single Comment (raises NotFound if missing).
    collection  -> returns dict {id: Comment}; if return_dict=False, a list.
    """
    db = c.db
    if _is_multi(id_or_ids):
        ids = list(id_or_ids)
        result = await comment_svc.get_by_ids(db, ids)
        if return_dict:
            return result
        return list(result.values())

    comment = await comment_svc.get_by_id(db, int(id_or_ids))
    if comment is None:
        raise NotFound(f'Comment {id_or_ids!r}')
    return comment


@classmethod
async def _comment_by_fullname(
    cls,
    fullname_or_names,
    data: bool = True,
    return_dict: bool = False,
):
    """Look up Comment(s) by fullname string(s) (e.g. ``'t1_abc'``).

    Single str  -> returns a single Comment (raises NotFound if missing).
    collection  -> returns dict {fullname: Comment}; if return_dict=False, a list.
    """
    db = c.db
    if _is_multi(fullname_or_names):
        names = list(fullname_or_names)
        result = {}
        for fn in names:
            comment = await comment_svc.get_by_fullname(db, fn)
            if comment is not None:
                result[fn] = comment
        if return_dict:
            return result
        return list(result.values())

    comment = await comment_svc.get_by_fullname(db, fullname_or_names)
    if comment is None:
        raise NotFound(f'Comment {fullname_or_names!r}')
    return comment


async def _comment_commit(self):
    """Persist in-memory changes and invalidate caches."""
    db = c.db
    await db.flush()
    comment_svc._cache_invalidate(self)
    comment_svc._cache_set(self)


# -- property shims ----------------------------------------------------------

def _comment_prop_id(self) -> int:
    return self.id

def _comment_prop_fullname(self) -> str:
    # The ORM model stores fullname as a column; fall back to computing it
    # from the id if the column is somehow empty (e.g. during creation).
    return self.fullname if self.fullname else f't1_{to36(self.id)}'

def _comment_prop_deleted(self) -> bool:
    return self.is_deleted

def _comment_prop_spam(self) -> bool:
    return self.is_spam

def _comment_prop_id36(self) -> str:
    return to36(self.id)

def _comment_prop_date(self) -> datetime:
    return self.date

def _comment_prop_age(self):
    return datetime.utcnow() - _naive(self.date)


# -- patch -------------------------------------------------------------------

_CommentORM._byID = _comment_byID
_CommentORM._by_fullname = _comment_by_fullname
_CommentORM._commit = _comment_commit

_CommentORM._id = property(_comment_prop_id)
_CommentORM._fullname = property(_comment_prop_fullname)
_CommentORM._deleted = property(_comment_prop_deleted)
_CommentORM._spam = property(_comment_prop_spam)
_CommentORM._id36 = property(_comment_prop_id36)
_CommentORM._date = property(_comment_prop_date)
_CommentORM._age = property(_comment_prop_age)

# Public name
Comment = _CommentORM


# ===========================================================================
# Message
# ===========================================================================

# -- classmethods ------------------------------------------------------------

@classmethod
async def _message_byID(
    cls,
    id_or_ids,
    data: bool = True,
    return_dict: bool = False,
    stale: bool = False,
):
    """Look up Message(s) by integer primary key.

    Single int  -> returns a single Message (raises NotFound if missing).
    collection  -> returns dict {id: Message}; if return_dict=False, a list.
    """
    db = c.db
    if _is_multi(id_or_ids):
        ids = list(id_or_ids)
        result = {}
        for mid in ids:
            msg = await message_svc.get_by_id(db, mid)
            if msg is not None:
                result[mid] = msg
        if return_dict:
            return result
        return list(result.values())

    msg = await message_svc.get_by_id(db, int(id_or_ids))
    if msg is None:
        raise NotFound(f'Message {id_or_ids!r}')
    return msg


@classmethod
async def _message_by_fullname(
    cls,
    fullname_or_names,
    data: bool = True,
    return_dict: bool = False,
):
    """Look up Message(s) by fullname string(s) (e.g. ``'t4_abc'``).

    Single str  -> returns a single Message (raises NotFound if missing).
    collection  -> returns dict {fullname: Message}; if return_dict=False, a list.
    """
    db = c.db

    async def _fetch_one(fn: str):
        # Decode the fullname to an id and use get_by_id.
        if not fn.startswith('t4_'):
            return None
        try:
            mid = from36(fn[3:])
        except (ValueError, TypeError):
            return None
        return await message_svc.get_by_id(db, mid)

    if _is_multi(fullname_or_names):
        names = list(fullname_or_names)
        result = {}
        for fn in names:
            msg = await _fetch_one(fn)
            if msg is not None:
                result[fn] = msg
        if return_dict:
            return result
        return list(result.values())

    msg = await _fetch_one(fullname_or_names)
    if msg is None:
        raise NotFound(f'Message {fullname_or_names!r}')
    return msg


async def _message_commit(self):
    """Persist in-memory changes and invalidate caches."""
    db = c.db
    await db.flush()
    message_svc._cache_invalidate(self)
    message_svc._cache_set(self)


# -- property shims ----------------------------------------------------------

def _message_prop_id(self) -> int:
    return self.id

def _message_prop_fullname(self) -> str:
    return self.fullname if self.fullname else f't4_{to36(self.id)}'

def _message_prop_deleted(self) -> bool:
    return self.is_deleted

def _message_prop_spam(self) -> bool:
    return self.is_spam

def _message_prop_id36(self) -> str:
    return to36(self.id)

def _message_prop_date(self) -> datetime:
    return self.date

def _message_prop_age(self):
    return datetime.utcnow() - _naive(self.date)


# -- patch -------------------------------------------------------------------

_MessageORM._byID = _message_byID
_MessageORM._by_fullname = _message_by_fullname
_MessageORM._commit = _message_commit

_MessageORM._id = property(_message_prop_id)
_MessageORM._fullname = property(_message_prop_fullname)
_MessageORM._deleted = property(_message_prop_deleted)
_MessageORM._spam = property(_message_prop_spam)
_MessageORM._id36 = property(_message_prop_id36)
_MessageORM._date = property(_message_prop_date)
_MessageORM._age = property(_message_prop_age)

# Public name
Message = _MessageORM


# ===========================================================================
# Dead-code stubs for removed Cassandra-backed classes
# ===========================================================================

class LinksByUrlAndSubreddit:
    """Legacy Cassandra index — removed.  Raises NotImplementedError on use."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'LinksByUrlAndSubreddit (Cassandra) has been removed. '
            'Use link_svc.get_by_url() instead.'
        )

    @classmethod
    def get_links(cls, url, sr=None):
        raise NotImplementedError


class CommentScoresByLink:
    """Legacy Cassandra index — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'CommentScoresByLink (Cassandra) has been removed.'
        )


class LinksByAccount:
    """Legacy Cassandra index — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'LinksByAccount (Cassandra) has been removed. '
            'Use link_svc.get_user_links() instead.'
        )


class CommentsByAccount:
    """Legacy Cassandra index — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'CommentsByAccount (Cassandra) has been removed. '
            'Use comment_svc.get_user_comments() instead.'
        )


class MessagesByAccount:
    """Legacy Cassandra index — removed."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            'MessagesByAccount (Cassandra) has been removed. '
            'Use message_svc.get_inbox() / message_svc.get_sent() instead.'
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    'Comment',
    'CommentScoresByLink',
    'CommentsByAccount',
    'Link',
    'LinksByAccount',
    'LinksByUrlAndSubreddit',
    'Message',
    'MessagesByAccount',
    'NotFound',
]
