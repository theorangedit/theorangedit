"""FastAPI health check router — ported from r2.controllers.health."""

import json
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException

import pylibmc
from r2.lib.app_globals import g
from r2.lib import promote, cache

router = APIRouter()


@router.get("/health")
async def health():
    if os.path.exists("/var/opt/reddit/quiesce"):
        raise HTTPException(status_code=503, detail="No thanks, I'm full.")
    return JSONResponse(g.versions, status_code=200)


@router.get("/health/promo")
async def promo_health():
    return JSONResponse(promote.health_check())


@router.get("/health/cache")
async def cache_health():
    results = {}
    behaviors = {
        "connect_timeout": 1000,
        "receive_timeout": int(1e6),
        "send_timeout": int(1e6),
    }
    for server in cache._CACHE_SERVERS:
        try:
            if server.startswith("udp:"):
                continue
            mc = pylibmc.Client([server], behaviors=behaviors)
            mc.get("__mcrouter__.version")
            results[server] = "OK"
        except pylibmc.Error as e:
            g.log.warning("Health check for %s FAILED: %s", server, e)
            results[server] = "FAILED %s" % e
    return JSONResponse(results)
