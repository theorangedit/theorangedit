"""
Native FastAPI router for all /api/v1/* endpoints — Phase D-3 step 3j.

Controllers covered:
  APIv1ScopesController  (apiv1/scopes.py)  — GET /api/v1/scopes
  APIv1LoginController   (apiv1/login.py)   — POST /api/v1/login|register
  APIv1UserController    (apiv1/user.py)    — GET/PATCH /api/v1/me, /api/v1/me/*
  APIv1GoldController    (apiv1/gold.py)    — POST /api/v1/gold/gild|give
  UserListListingController                 — GET /api/v1/me/friends

Route ordering (Starlette first-match wins within this router):
  1. /api/v1/gold/*        — literal prefix, most specific
  2. /api/v1/user/{}/trophies — 4-segment, literal 'trophies'
  3. /api/v1/scopes        — explicit named endpoint
  4. /api/v1/login|register— explicit named POSTs
  5. /api/v1/me            — literal 'me' path
  6. /api/v1/me/friends/{username} — 5-segment (before me/{action})
  7. /api/v1/me/friends    — literal 'friends' (friends list)
  8. /api/v1/me/prefs      — literal 'prefs' (GET + PATCH)
  9. /api/v1/me/karma|trophies — literal named endpoints
 10. /api/v1/me/{action}   — generic apiv1user catch-all
"""

import inspect

from fastapi import APIRouter, Request
from starlette.responses import Response

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _call(coro_or_val):
    if inspect.isawaitable(coro_or_val):
        return await coro_or_val
    return coro_or_val


def _to_response(result, request: Request) -> Response:
    if result is None:
        return Response(status_code=200)
    if isinstance(result, (str, bytes)):
        from r2.lib.context import c as _c
        content_type = (
            getattr(_c, 'content_type', None)
            or getattr(request.state, 'content_type', None)
            or 'text/html; charset=UTF-8'
        )
        return Response(content=result, media_type=content_type)
    return result


# ---------------------------------------------------------------------------
# APIv1GoldController — POST /api/v1/gold/gild/:fullname  and  /give/:username
# ---------------------------------------------------------------------------

@router.post("/api/v1/gold/gild/{fullname}")
async def POST_gild(fullname: str, request: Request):
    from r2.controllers.apiv1.gold import APIv1GoldController
    return _to_response(
        await _call(APIv1GoldController().POST_gild(fullname=fullname)), request)


@router.post("/api/v1/gold/give/{username}")
async def POST_give(username: str, request: Request):
    from r2.controllers.apiv1.gold import APIv1GoldController
    return _to_response(
        await _call(APIv1GoldController().POST_give(username=username)), request)


# ---------------------------------------------------------------------------
# APIv1UserController — GET /api/v1/user/:username/trophies
# ---------------------------------------------------------------------------

@router.get("/api/v1/user/{username}/trophies")
async def GET_usertrophies(username: str, request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_usertrophies(username=username)),
        request)


# ---------------------------------------------------------------------------
# APIv1ScopesController — GET /api/v1/scopes
# ---------------------------------------------------------------------------

@router.get("/api/v1/scopes")
async def GET_scopes(request: Request):
    from r2.controllers.apiv1.scopes import APIv1ScopesController
    return _to_response(
        await _call(APIv1ScopesController().GET_scopes()), request)


# ---------------------------------------------------------------------------
# APIv1LoginController — POST /api/v1/login  and  /api/v1/register
# ---------------------------------------------------------------------------

@router.post("/api/v1/login")
async def POST_v1_login(request: Request):
    from r2.controllers.apiv1.login import APIv1LoginController
    return _to_response(
        await _call(APIv1LoginController().POST_login()), request)


@router.post("/api/v1/register")
async def POST_v1_register(request: Request):
    from r2.controllers.apiv1.login import APIv1LoginController
    return _to_response(
        await _call(APIv1LoginController().POST_register()), request)


# ---------------------------------------------------------------------------
# APIv1UserController — /api/v1/me  (the top-level "me" endpoint)
# ---------------------------------------------------------------------------

@router.get("/api/v1/me")
async def GET_me(request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_me()), request)


# ---------------------------------------------------------------------------
# APIv1UserController — /api/v1/me/friends/:username  (GET, PUT, DELETE)
# Must be registered before /api/v1/me/{action} (same depth).
# ---------------------------------------------------------------------------

@router.get("/api/v1/me/friends/{username}")
async def GET_friend(username: str, request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_friends(username=username)),
        request)


@router.put("/api/v1/me/friends/{username}")
async def PUT_friend(username: str, request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().PUT_friends(username=username)),
        request)


@router.delete("/api/v1/me/friends/{username}")
async def DELETE_friend(username: str, request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().DELETE_friends(username=username)),
        request)


# ---------------------------------------------------------------------------
# UserListListingController — GET /api/v1/me/friends  (friends list page)
# Before /api/v1/me/{action} catch-all.
# ---------------------------------------------------------------------------

@router.get("/api/v1/me/friends")
async def GET_me_friends_list(request: Request):
    from r2.controllers.listingcontroller import UserListListingController
    return _to_response(
        await _call(UserListListingController().GET_user_prefs(where='friends')),
        request)


# ---------------------------------------------------------------------------
# APIv1UserController — /api/v1/me/prefs  (GET + PATCH)
# Must be before /api/v1/me/{action} catch-all.
# ---------------------------------------------------------------------------

@router.get("/api/v1/me/prefs")
async def GET_prefs(request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_prefs()), request)


@router.patch("/api/v1/me/prefs")
async def PATCH_prefs(request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().PATCH_prefs()), request)


# ---------------------------------------------------------------------------
# APIv1UserController — /api/v1/me/karma  and  /api/v1/me/trophies
# ---------------------------------------------------------------------------

@router.get("/api/v1/me/karma")
async def GET_karma(request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_karma()), request)


@router.get("/api/v1/me/trophies")
async def GET_me_trophies(request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_trophies()), request)


# ---------------------------------------------------------------------------
# APIv1UserController — generic /api/v1/me/{action} catch-all
# Handles any remaining me/* actions not matched above.
# ---------------------------------------------------------------------------

@router.get("/api/v1/me/{action}")
async def GET_me_action(action: str, request: Request):
    from r2.controllers.apiv1.user import APIv1UserController
    return _to_response(
        await _call(APIv1UserController().GET_me()), request)
