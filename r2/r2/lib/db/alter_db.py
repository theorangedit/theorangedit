"""
r2.lib.db.alter_db
~~~~~~~~~~~~~~~~~~

Legacy maintenance script for Thing EAV SQL table alterations.
The underlying tables (thing_table, data_table, rel_table) were removed
with the tdb_sql/Thing ORM. This module is a no-op stub retained only so
that existing import sites compile.
"""


def thing_tables():
    return iter([])


def rel_tables():
    return iter([])


def dtables():
    return iter([])


def exec_all(command, data=False, rel=False, print_only=False):
    raise NotImplementedError("alter_db: Thing SQL tables removed — use Alembic migrations")
