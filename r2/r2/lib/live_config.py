"""
PostgreSQL-backed live configuration — replaces ZooKeeper LiveConfig.

The `live_config` table (defined in r2.models.orm.misc.LiveConfig) holds
key/value pairs that can be updated at runtime via the admin API.  On
startup and on demand, values are loaded into g.live_config (the existing
ConfigValueParser dict) so the rest of the app continues to work without
changes.

Key convention: same keys as the [live_config] INI section.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from r2.lib.app_globals import Globals

log = logging.getLogger(__name__)


async def refresh_live_config(db: AsyncSession, g: "Globals") -> None:
    """Load all rows from live_config table into g.live_config.

    Values in the DB take precedence over INI values.  Unknown keys are
    silently ignored — they may belong to a plugin not loaded in this process.
    """
    from r2.models.orm.misc import LiveConfig as LiveConfigRow

    rows = (await db.execute(select(LiveConfigRow))).scalars().all()
    updated = 0
    for row in rows:
        if row.key in g.live_config:
            try:
                g.live_config[row.key] = row.value
                updated += 1
            except Exception:
                pass  # type coercion failure — skip
    if updated:
        log.debug("live_config: refreshed %d keys from PostgreSQL", updated)


async def set_live_config(db: AsyncSession, key: str, value: str) -> None:
    """Upsert a single live_config key (admin API endpoint handler)."""
    from r2.models.orm.misc import LiveConfig as LiveConfigRow

    stmt = pg_insert(LiveConfigRow).values(key=key, value=value).on_conflict_do_update(
        index_elements=['key'],
        set_={'value': value, 'updated_at': LiveConfigRow.updated_at},
    )
    await db.execute(stmt)


async def get_all(db: AsyncSession) -> dict[str, str]:
    """Return all live_config rows as a plain dict."""
    from r2.models.orm.misc import LiveConfig as LiveConfigRow

    rows = (await db.execute(select(LiveConfigRow))).scalars().all()
    return {row.key: row.value for row in rows}
