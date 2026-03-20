"""
Native FastAPI router for all listing endpoints — Phase D-3 step 3g.

Strategy: each handler instantiates the appropriate controller class and
delegates to its GET_listing (or other) method.  The controller's
@validate-wrapped methods extract validated params from the request context
set by RedditRequestMiddleware; path params from FastAPI are passed as extra
keyword args that flow into the @validate env dict (the Validator base class
checks the env dict as a fallback via self.url=True).

Namespaces migrated here (entire namespace owned by listing controllers):
  /                    → HotController
  /hot /new /rising /randomrising /ads /top /controversial
  /by_id/{names}       → ByIDController
  /comments[/gilded]   → CommentsController / GildedController
  /gilded              → GildedController
  /saved               → UserController.GET_saved_redirect
  /user/*              → UserController  (entire /user/ namespace)
  /message/*           → MessageController  (entire /message/ namespace)
  /user/{u}/m/{mp}/*   → multi-context listing controllers
  /me/m/{mp}/*         → multi-context listing controllers
  /me/f/{fn}/*         → filter-context listing controllers

Namespaces NOT migrated (shared with un-migrated front.py / forms.py):
  /about/*  /subreddits/*  /reddits/*  /prefs/*  /api/v1/me/*
  → left in legacy dispatcher until those controllers are ported (step 3h-j)

Route ordering note: Starlette matches routes in registration order; the FIRST
matching route wins.  More-specific routes (with literal path segments) must
therefore be registered BEFORE generic parameterised catch-alls that cover the
same depth.  The critical ordering concern here is inside the /user/ tree:
  /user/{username}/m/{multipath}  (literal "m")  — BEFORE
  /user/{username}/{where}/{show}  (all params, same depth)
"""

import inspect

from fastapi import APIRouter, Request
from starlette.responses import Response

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _call(coro_or_val):
    """Await a value if it is a coroutine."""
    if inspect.isawaitable(coro_or_val):
        return await coro_or_val
    return coro_or_val


def _to_response(result, request: Request) -> Response:
    """Convert a controller return value to a Starlette Response.

    Mirrors the normalisation used in all routers:
      None         → 200 empty
      str / bytes  → Response with c.content_type (default text/html)
      Response     → pass-through (covers RedirectResponse, JSONResponse, …)
    """
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
# Root and simple sort listings
# Routes: /, /hot, /new, /rising, /randomrising, /ads, /top, /controversial
# Entire-namespace: yes — no other controllers share these paths.
# ---------------------------------------------------------------------------

@router.get("/")
async def GET_index(request: Request):
    from r2.controllers.listingcontroller import HotController
    return _to_response(await _call(HotController().GET_listing()), request)


@router.get("/hot")
async def GET_hot(request: Request):
    from r2.controllers.listingcontroller import HotController
    return _to_response(await _call(HotController().GET_listing()), request)


@router.get("/new")
async def GET_new(request: Request):
    from r2.controllers.listingcontroller import NewController
    return _to_response(await _call(NewController().GET_listing()), request)


@router.post("/new")
async def POST_new(request: Request):
    from r2.controllers.listingcontroller import NewController
    return _to_response(await _call(NewController().POST_listing()), request)


@router.get("/rising")
async def GET_rising(request: Request):
    from r2.controllers.listingcontroller import RisingController
    return _to_response(await _call(RisingController().GET_listing()), request)


@router.get("/randomrising")
async def GET_randomrising(request: Request):
    from r2.controllers.listingcontroller import RandomrisingController
    return _to_response(
        await _call(RandomrisingController().GET_listing()), request)


@router.get("/ads")
async def GET_ads(request: Request):
    from r2.controllers.listingcontroller import AdsController
    return _to_response(await _call(AdsController().GET_listing()), request)


@router.get("/top")
async def GET_top(request: Request):
    from r2.controllers.listingcontroller import BrowseController
    return _to_response(
        await _call(BrowseController().GET_listing(sort='top')), request)


@router.post("/top")
async def POST_top(request: Request):
    from r2.controllers.listingcontroller import BrowseController
    return _to_response(
        await _call(BrowseController().POST_listing(sort='top')), request)


@router.get("/controversial")
async def GET_controversial(request: Request):
    from r2.controllers.listingcontroller import BrowseController
    return _to_response(
        await _call(BrowseController().GET_listing(sort='controversial')),
        request)


@router.post("/controversial")
async def POST_controversial(request: Request):
    from r2.controllers.listingcontroller import BrowseController
    return _to_response(
        await _call(BrowseController().POST_listing(sort='controversial')),
        request)


# ---------------------------------------------------------------------------
# By-ID listing — /by_id/{names}
# ---------------------------------------------------------------------------

@router.get("/by_id/{names}")
async def GET_by_id(names: str, request: Request):
    from r2.controllers.listingcontroller import ByIDController
    return _to_response(
        await _call(ByIDController().GET_listing(names=names)), request)


# ---------------------------------------------------------------------------
# Comments and gilded
# /comments/gilded registered BEFORE /comments (more specific path first).
# ---------------------------------------------------------------------------

@router.get("/comments/gilded")
async def GET_comments_gilded(request: Request):
    from r2.controllers.listingcontroller import GildedController
    return _to_response(await _call(GildedController().GET_listing()), request)


@router.get("/comments")
async def GET_comments(request: Request):
    from r2.controllers.listingcontroller import CommentsController
    return _to_response(
        await _call(CommentsController().GET_listing()), request)


@router.get("/gilded")
async def GET_gilded(request: Request):
    from r2.controllers.listingcontroller import GildedController
    return _to_response(await _call(GildedController().GET_listing()), request)


# ---------------------------------------------------------------------------
# Saved redirect — /saved
# ---------------------------------------------------------------------------

@router.get("/saved")
async def GET_saved(request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_saved_redirect()), request)


# ---------------------------------------------------------------------------
# Multi-context listing helpers
#
# /user/{u}/m/{mp}/*, /me/m/{mp}/*, /me/f/{fn}/*
#
# These are registered INSIDE the user section so they appear before
# /user/{username}/{where}/{show} (same path depth, but literal "m" here).
# Starlette first-match wins, so literal-segment routes must come first.
# ---------------------------------------------------------------------------

_MULTI_CTRL_MAP = {
    'hot': 'HotController',
    'new': 'NewController',
    'rising': 'RisingController',
    'randomrising': 'RandomrisingController',
    'ads': 'AdsController',
}


async def _multi_listing(sort: str, request: Request) -> Response:
    """Dispatch a multi/filter-context listing by sort name."""
    import r2.controllers.listingcontroller as _lc
    if sort in ('top', 'controversial'):
        result = await _call(_lc.BrowseController().GET_listing(sort=sort))
    else:
        ctrl_cls = getattr(_lc, _MULTI_CTRL_MAP.get(sort, 'HotController'))
        result = await _call(ctrl_cls().GET_listing())
    return _to_response(result, request)


# ---------------------------------------------------------------------------
# User routes — entire /user/ namespace belongs to UserController.
#
# ORDERING IS CRITICAL — must match from most-specific to least-specific:
#
#  1. /user/me                        literal "me" in position 2
#  2. /user/me/{rest:path}            literal "me", greedy tail
#  3. /user/{u}/about                 literal "about" in position 3
#  4. /user/{u}/trophies              literal "trophies" in position 3
#  5. /user/{u}/m/{mp}/              literal "m", trailing slash (4-seg)
#  6. /user/{u}/m/{mp}               literal "m" in position 3 (4-seg)
#  7. /user/{u}/m/{mp}/{sort}        literal "m" (5-seg)
#  8. /user/{u}/saved/{category}     literal "saved" in position 3 (4-seg)
#  9. /user/{u}/{where}/{show}        all-param (4-seg)   ← after literal-m routes
# 10. /user/{u}/{where}              all-param catch-all (3-seg)
# ---------------------------------------------------------------------------

@router.get("/user/me")
async def GET_user_me(request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_rel_user_redirect(rest="")), request)


@router.get("/user/me/{rest:path}")
async def GET_user_me_rest(rest: str, request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_rel_user_redirect(rest=rest)), request)


@router.get("/user/{username}/about")
async def GET_user_about(username: str, request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_about(username=username)), request)


@router.get("/user/{username}/trophies")
async def GET_user_trophies(username: str, request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_trophies(username=username)), request)


# Multi routes — must precede /{where}/{show} and /{where} (same depth)
@router.get("/user/{username}/m/{multipath}/")
@router.get("/user/{username}/m/{multipath}")
async def GET_user_multi_hot(username: str, multipath: str, request: Request):
    from r2.controllers.listingcontroller import HotController
    return _to_response(await _call(HotController().GET_listing()), request)


@router.get("/user/{username}/m/{multipath}/submit")
async def GET_user_multi_submit(username: str, multipath: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_submit()), request)


@router.get("/user/{username}/m/{multipath}/{sort}")
async def GET_user_multi_sort(username: str, multipath: str, sort: str,
                               request: Request):
    return await _multi_listing(sort, request)


@router.get("/user/{username}/saved/{category}")
async def GET_user_saved_category(username: str, category: str,
                                  request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_listing(
            where="saved", username=username, category=category)),
        request)


# Generic 4-segment user routes — after all literal-segment routes above
@router.get("/user/{username}/{where}/{show}")
async def GET_user_where_show(username: str, where: str, show: str,
                               request: Request):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_listing(
            where=where, username=username, show=show)),
        request)


# Generic 3-segment user route — catch-all, must be last in /user/ block
@router.get("/user/{username}/{where}")
async def GET_user_where(username: str, where: str = "overview",
                          request: Request = None):
    from r2.controllers.listingcontroller import UserController
    return _to_response(
        await _call(UserController().GET_listing(
            where=where, username=username)),
        request)


# ---------------------------------------------------------------------------
# /me/m/* and /me/f/* — multi and filter context listing routes
# ---------------------------------------------------------------------------

@router.get("/me/m/{multipath}/")
@router.get("/me/m/{multipath}")
async def GET_me_multi_hot(multipath: str, request: Request):
    from r2.controllers.listingcontroller import HotController
    return _to_response(await _call(HotController().GET_listing()), request)


@router.get("/me/m/{multipath}/submit")
async def GET_me_multi_submit(multipath: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_submit()), request)


@router.get("/me/m/{multipath}/{sort}")
async def GET_me_multi_sort(multipath: str, sort: str, request: Request):
    return await _multi_listing(sort, request)


@router.get("/me/f/{filtername}/")
@router.get("/me/f/{filtername}")
async def GET_filter_hot(filtername: str, request: Request):
    from r2.controllers.listingcontroller import HotController
    return _to_response(await _call(HotController().GET_listing()), request)


@router.get("/me/f/{filtername}/submit")
async def GET_filter_submit(filtername: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_submit()), request)


@router.get("/me/f/{filtername}/{sort}")
async def GET_filter_sort(filtername: str, sort: str, request: Request):
    return await _multi_listing(sort, request)


# ---------------------------------------------------------------------------
# Message routes — entire /message/ namespace belongs to MessageController.
#
# Ordering: specific paths before the generic /{where} catch-all.
#   /message/compose         literal
#   /message/messages/{mid}  literal "messages"
#   /message/moderator/{sub} literal "moderator"
#   /message/{where}         catch-all
# ---------------------------------------------------------------------------

@router.get("/message/compose")
async def GET_message_compose(request: Request):
    from r2.controllers.listingcontroller import MessageController
    return _to_response(
        await _call(MessageController().GET_compose()), request)


@router.get("/message/messages/{mid}")
async def GET_message_by_id(mid: str, request: Request):
    from r2.controllers.listingcontroller import MessageController
    return _to_response(
        await _call(MessageController().GET_listing(where="messages", mid=mid)),
        request)


@router.get("/message/moderator/{subwhere}")
async def GET_message_moderator(subwhere: str, request: Request):
    from r2.controllers.listingcontroller import MessageController
    return _to_response(
        await _call(MessageController().GET_listing(
            where="moderator", subwhere=subwhere)),
        request)


@router.get("/message/{where}")
async def GET_message(where: str, request: Request):
    from r2.controllers.listingcontroller import MessageController
    return _to_response(
        await _call(MessageController().GET_listing(where=where)), request)


# Note: /about/message/{where} (subreddit-scoped modmail) is in the /about/*
# namespace shared with un-migrated front.py routes.  Left for legacy
# dispatcher until front.py is ported in step 3h.
