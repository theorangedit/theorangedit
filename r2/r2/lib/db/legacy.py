"""
r2.lib.db.legacy
~~~~~~~~~~~~~~~~

Consolidated compatibility shims for the legacy Thing EAV ORM and tdb_sql
layer, previously split across thing.py and tdb_sql.py.

These stubs are retained only so that existing import sites compile after
those files are removed. All stubs raise NotImplementedError if called, or
are no-ops used only for isinstance() checks and SQLAlchemy table setup.
"""
from __future__ import annotations

import sqlalchemy as sa


# ── Exceptions ────────────────────────────────────────────────────────────────

class NotFound(Exception):
    pass


class CreationError(Exception):
    pass


# ── Thing-layer stub classes ──────────────────────────────────────────────────

class Thing:
    """Legacy Thing ORM base — stub. Use r2.services.* instead."""

    _cache = None
    _defaults = {}

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Thing ORM removed — use the service layer (r2.services.*)")

    @classmethod
    def _byID(cls, ids, *args, **kwargs):
        raise NotImplementedError(f"{cls.__name__}._byID: Thing ORM removed")

    @classmethod
    def _by_fullname(cls, name, *args, **kwargs):
        raise NotImplementedError(
            f"{cls.__name__}._by_fullname: Thing ORM removed")

    @classmethod
    def _query(cls, *args, **kwargs):
        raise NotImplementedError(f"{cls.__name__}._query: Thing ORM removed")

    def _commit(self):
        raise NotImplementedError("Thing._commit: Thing ORM removed")


class Relation:
    """Legacy Relation ORM base — stub."""

    @classmethod
    def fast_query(cls, *args, **kwargs):
        raise NotImplementedError("Relation.fast_query: Thing ORM removed")


class MultiRelation:
    """Legacy MultiRelation — stub."""
    pass


class Query:
    """Legacy query object — stub (used in isinstance checks)."""

    def __init__(self, *args, **kwargs):
        pass

    def __iter__(self):
        return iter([])


class Merge:
    """Legacy Merge query — stub (used in isinstance checks)."""

    def __init__(self, *args, **kwargs):
        pass

    def __iter__(self):
        return iter([])


class Relations:
    """Legacy Relations helper — stub."""
    pass


# ── tdb_sql shims ─────────────────────────────────────────────────────────────

def make_metadata(engine=None) -> sa.MetaData:
    """Return an unbound SQLAlchemy MetaData (SA 2.x compatible).

    The ``engine`` argument is accepted for backwards-compatibility but
    ignored — SA 2.x does not support engine-bound metadata.
    """
    return sa.MetaData()


def index_str(table: sa.Table, name: str, col: str) -> sa.Index:
    """Return a SQLAlchemy Index for ``table.c[col]``."""
    return sa.Index(f'idx_{table.name}_{name}', table.c[col])


def create_table(table: sa.Table, indices=None) -> None:
    """No-op: schema creation is handled by Alembic migrations."""
    pass
