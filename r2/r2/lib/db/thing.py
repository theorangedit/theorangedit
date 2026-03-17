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
thing.py — compatibility stub replacing the legacy Thing EAV ORM.

All actual model classes now live in r2.models.orm.* and are accessed via
r2.services.*. This module exports only the names that remaining callers
import so that those imports succeed; actual usage will raise errors.
"""


# ── Exceptions ────────────────────────────────────────────────────────────────

class NotFound(Exception):
    pass


class CreationError(Exception):
    pass


# ── Legacy base classes — stubs ───────────────────────────────────────────────

class Thing:
    """Legacy Thing ORM base — no longer functional. Use r2.services.*."""

    _cache = None
    _data_int_props = ()
    _int_prop_suffix = ''
    _essentials = ()
    _defaults = {}

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Thing ORM has been removed. Use the service layer (r2.services.*)."
        )

    @classmethod
    def _byID(cls, ids, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}._byID: Thing ORM removed. Use r2.services.*."
        )

    @classmethod
    def _by_fullname(cls, name, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}._by_fullname: Thing ORM removed. Use r2.services.*."
        )

    @classmethod
    def _query(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}._query: Thing ORM removed. Use r2.services.*."
        )

    def _commit(self):
        raise NotImplementedError(
            "Thing._commit: Thing ORM removed. Use r2.services.*."
        )


class Relation:
    """Legacy Relation ORM base — stub."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    @classmethod
    def fast_query(cls, *args, **kwargs):
        raise NotImplementedError(
            "Relation.fast_query: Thing ORM removed. Use r2.services.*."
        )


class MultiRelation:
    """Legacy MultiRelation — stub."""
    pass


# ── Query objects ─────────────────────────────────────────────────────────────

class Query:
    """Legacy query object — stub."""

    def __init__(self, *args, **kwargs):
        pass

    def __iter__(self):
        return iter([])


class Merge:
    """Legacy Merge query — stub."""

    def __init__(self, *args, **kwargs):
        pass

    def __iter__(self):
        return iter([])


class Relations:
    """Legacy Relations helper — stub."""
    pass
