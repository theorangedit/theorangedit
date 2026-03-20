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
r2.main — FastAPI application entry point.

This module creates the FastAPI ``app`` instance and registers all routers.
It replaces the old Pylons ``make_app`` + ``RedditApp`` + Routes setup.

Usage (uvicorn):
    uvicorn r2.main:app --host 0.0.0.0 --port 8080

Usage (gunicorn with uvicorn workers):
    gunicorn r2.main:app -k uvicorn.workers.UvicornWorker

The ``app`` object here is the *bare* FastAPI instance.  Middleware is added
by ``r2.config.middleware.make_app()`` which is called on startup by the WSGI
server entrypoint or by tests.
"""

import _strptime  # pre-import to avoid threading issues (see r2/__init__.py)

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="theorangedit",
    description="Reddit open-source fork running on Python 3 / FastAPI",
    version="1.0.0",
    # Disable automatic /docs and /redoc in production — override via env
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """
    Application startup hook — runs after the event loop starts.

    Handles async initialisation that cannot be done synchronously during
    load_environment() (e.g. Redis connection, async DB engine).
    """
    from r2.lib.app_globals import g

    # ── Async DB engine ──────────────────────────────────────────────────────
    from r2.lib.db.engine import init_engine
    db_url = g.config.get("r2.db_url", "postgresql+asyncpg://reddit:password@postgres:5432/reddit")
    init_engine(db_url)

    # ── Redis listing cache ───────────────────────────────────────────────────
    try:
        import redis.asyncio as aioredis
        g.redis = aioredis.from_url(
            g.redis_url,
            encoding="utf-8",
            decode_responses=False,
        )
        await g.redis.ping()
        g.log.info("Redis connected: %s", g.redis_url)
    except Exception as exc:
        g.log.warning(
            "Redis unavailable (%s) — listing cache will fall back to PostgreSQL", exc
        )
        g.redis = None

    # ── Live config from PostgreSQL (async refresh) ───────────────────────────
    try:
        from r2.lib.live_config import refresh_live_config
        from r2.lib.db.engine import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await refresh_live_config(db, g)
    except Exception as exc:
        g.log.warning("live_config PostgreSQL refresh failed (%s), using INI values", exc)


@app.on_event("shutdown")
async def shutdown_event():
    from r2.lib.app_globals import g
    if getattr(g, 'redis', None):
        await g.redis.aclose()


# ---------------------------------------------------------------------------
# Routers
#
# Each router module wraps the corresponding old Pylons controller.  During
# the incremental migration, routers are added here one by one.  Until a
# controller is fully ported, its Pylons-style methods remain in place and
# are called via the router adapter pattern in r2.lib.controller_adapter.
# ---------------------------------------------------------------------------

# Health / meta
from r2.controllers.fastapi import health, error  # noqa: E402

app.include_router(health.router, tags=["meta"])
app.include_router(error.router, tags=["meta"])

# Native FastAPI routers — Phase D-3/D-4 complete.
from r2.routers import api as api_router  # noqa: E402
from r2.routers import apiv1 as apiv1_router  # noqa: E402
from r2.routers import buttons as buttons_router  # noqa: E402
from r2.routers import embed as embed_router  # noqa: E402
from r2.routers import front as front_router  # noqa: E402
from r2.routers import ipn as ipn_router  # noqa: E402
from r2.routers import listing as listing_router  # noqa: E402
from r2.routers import misc as misc_router  # noqa: E402
from r2.routers import multi as multi_router  # noqa: E402
from r2.routers import oauth2 as oauth2_router  # noqa: E402
from r2.routers import promote as promote_router  # noqa: E402
from r2.routers import wiki as wiki_router  # noqa: E402

app.include_router(api_router.router, tags=["api"])
app.include_router(apiv1_router.router, tags=["apiv1"])
app.include_router(buttons_router.router, tags=["buttons"])
app.include_router(embed_router.router, tags=["embed"])
app.include_router(listing_router.router, tags=["listings"])
app.include_router(front_router.router, tags=["front"])
app.include_router(multi_router.router, tags=["multis"])
app.include_router(oauth2_router.router, tags=["oauth2"])
app.include_router(wiki_router.router, tags=["wiki"])
app.include_router(ipn_router.router, tags=["ipn"])
app.include_router(promote_router.router, tags=["promote"])
app.include_router(misc_router.router, tags=["misc"])
# misc_router's /{url:path} catch-all handles all remaining requests (D-4)
