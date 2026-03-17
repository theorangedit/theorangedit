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
    Application startup hook.

    The Globals singleton (g) is already initialised synchronously by
    make_app() -> load_environment() before uvicorn starts.  This hook is
    available for any async initialisation needed after the event loop starts
    (e.g. async DB connection pools).
    """
    pass


@app.on_event("shutdown")
async def shutdown_event():
    pass


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


# ---------------------------------------------------------------------------
# Fallback: catch-all that defers to the legacy routing table
# ---------------------------------------------------------------------------

from r2.controllers.fastapi.legacy_dispatcher import router as legacy_router  # noqa: E402
app.include_router(legacy_router)
