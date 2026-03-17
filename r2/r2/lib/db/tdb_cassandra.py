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
tdb_cassandra.py — compatibility stub replacing the Cassandra client layer.

Cassandra has been removed from the stack (Phase 10). All data previously
stored in Cassandra now lives in PostgreSQL (relations tables) or Redis
(listing cache). This module exports stub names so that remaining import
statements in code that has not yet been fully migrated will not fail at
import time.
"""


# ── Exceptions ────────────────────────────────────────────────────────────────

class NotFound(Exception):
    pass


# ── Consistency levels ────────────────────────────────────────────────────────

class CL:
    ONE = 'ONE'
    QUORUM = 'QUORUM'
    ALL = 'ALL'


# ── Decorators ────────────────────────────────────────────────────────────────

def will_write(fn):
    """No-op decorator (was used to pick write CL in old Cassandra code)."""
    return fn


# ── ThingMeta ─────────────────────────────────────────────────────────────────

class ThingMeta(type):
    """Legacy metaclass — no-op."""
    pass


# ── max_column_count ──────────────────────────────────────────────────────────

max_column_count = 100_000


# ── view_of decorator ─────────────────────────────────────────────────────────

def view_of(cls):
    """No-op class decorator."""
    def decorator(view_cls):
        return view_cls
    return decorator


# ── Base Thing/View classes ───────────────────────────────────────────────────

class _CassandraBase:
    _use_db = False
    _connection_pool = None
    _read_consistency_level = CL.ONE
    _write_consistency_level = CL.QUORUM
    _extra_schema_creation_args = {}

    @classmethod
    def _byID(cls, ids, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}: Cassandra removed. Use service layer."
        )

    @classmethod
    def _by_fullname(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}: Cassandra removed. Use service layer."
        )

    @classmethod
    def _set_values(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}._set_values: Cassandra removed."
        )

    @classmethod
    def _get_column(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}._get_column: Cassandra removed."
        )

    @classmethod
    def get_time_sorted_columns(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}.get_time_sorted_columns: Cassandra removed."
        )

    @classmethod
    def fast_query(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}.fast_query: Cassandra removed."
        )

    def _commit(self):
        raise NotImplementedError(
            f"{self.__class__.__name__}._commit: Cassandra removed."
        )


class Thing(_CassandraBase):
    """Cassandra Thing base — stub."""
    _ttl = None
    _bool_props = ()
    _int_props = ()
    _float_props = ()
    _str_props = ()


class UuidThing(Thing):
    """Cassandra UuidThing base — stub."""
    pass


class View(_CassandraBase):
    """Cassandra View base — stub."""
    _value_type = None


class DenormalizedRelation(_CassandraBase):
    """Cassandra DenormalizedRelation — stub."""

    @classmethod
    def create(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}.create: Cassandra removed."
        )

    @classmethod
    def destroy(cls, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}.destroy: Cassandra removed."
        )


# ── MultiColumnQuery ──────────────────────────────────────────────────────────

class MultiColumnQuery:
    """Cassandra multi-column query — stub."""

    def __init__(self, *args, **kwargs):
        pass

    def __iter__(self):
        return iter([])
