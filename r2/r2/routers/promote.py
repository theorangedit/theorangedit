"""
Native FastAPI router for advertising / promoted-link endpoints — Phase D-3 step 3j.

Controllers covered:
  PromoteController        (promotecontroller.py) — /promoted/new_promo, /edit_promo/:link,
                                                     /pay/:link/:campaign, /refund/:link/:campaign
  PromoteListingController (promotecontroller.py) — /promoted/, /promoted/:sort
  SponsorController        (promotecontroller.py) — /sponsor/report, /inventory, /lookup_user
  SponsorListingController (promotecontroller.py) — /sponsor, /sponsor/promoted/*, /sponsor/promoted/:sort

Route ordering notes (Starlette first-match within this router):
  - Under /promoted/*: literal names (new_promo, edit_promo, pay, refund) registered
    BEFORE the /{sort} catch-all so they are not consumed as a sort value.
  - Under /sponsor/promoted/*: literal `live_promos/{sr}` registered BEFORE `/{sort}`
    (live_promos is also a valid sort value; with an sr path param it's 4 segments vs 3).
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
# PromoteController — editing endpoints
# Registered BEFORE /promoted/{sort} so literal segments win.
# ---------------------------------------------------------------------------

@router.get("/promoted/new_promo")
async def GET_new_promo(request: Request):
    from r2.controllers.promotecontroller import PromoteController
    return _to_response(
        await _call(PromoteController().GET_new_promo()), request)


@router.get("/promoted/edit_promo/{link}")
async def GET_edit_promo(link: str, request: Request):
    from r2.controllers.promotecontroller import PromoteController
    return _to_response(
        await _call(PromoteController().GET_edit_promo(link=link)), request)


@router.get("/promoted/pay/{link}/{campaign}")
async def GET_pay(link: str, campaign: str, request: Request):
    from r2.controllers.promotecontroller import PromoteController
    return _to_response(
        await _call(PromoteController().GET_pay(link=link, campaign=campaign)),
        request)


@router.get("/promoted/refund/{link}/{campaign}")
async def GET_refund(link: str, campaign: str, request: Request):
    from r2.controllers.promotecontroller import PromoteController
    return _to_response(
        await _call(PromoteController().GET_refund(link=link, campaign=campaign)),
        request)


# ---------------------------------------------------------------------------
# PromoteListingController — /promoted/  and  /promoted/:sort
# ---------------------------------------------------------------------------

@router.get("/promoted/")
async def GET_promoted_index(request: Request):
    from r2.controllers.promotecontroller import PromoteListingController
    return _to_response(
        await _call(PromoteListingController().GET_listing(sort='all')), request)


@router.get("/promoted/{sort}")
async def GET_promoted_sort(sort: str, request: Request):
    from r2.controllers.promotecontroller import PromoteListingController
    return _to_response(
        await _call(PromoteListingController().GET_listing(sort=sort)), request)


# ---------------------------------------------------------------------------
# SponsorController — literal management endpoints
# Registered before /sponsor/promoted/* parameterised routes.
# ---------------------------------------------------------------------------

@router.get("/sponsor/report")
async def GET_sponsor_report(request: Request):
    from r2.controllers.promotecontroller import SponsorController
    return _to_response(
        await _call(SponsorController().GET_report()), request)


@router.get("/sponsor/inventory")
async def GET_sponsor_inventory(request: Request):
    from r2.controllers.promotecontroller import SponsorController
    return _to_response(
        await _call(SponsorController().GET_promote_inventory()), request)


@router.get("/sponsor/lookup_user")
async def GET_sponsor_lookup_user(request: Request):
    from r2.controllers.promotecontroller import SponsorController
    return _to_response(
        await _call(SponsorController().GET_lookup_user()), request)


# ---------------------------------------------------------------------------
# SponsorListingController — /sponsor/promoted/live_promos/:sr
# Registered BEFORE /sponsor/promoted/:sort (live_promos has an extra segment).
# ---------------------------------------------------------------------------

@router.get("/sponsor/promoted/live_promos/{sr}")
async def GET_sponsor_live_promos_sr(sr: str, request: Request):
    from r2.controllers.promotecontroller import SponsorListingController
    return _to_response(
        await _call(SponsorListingController().GET_listing(
            sort='live_promos', srname=sr)),
        request)


# ---------------------------------------------------------------------------
# SponsorListingController — /sponsor/promoted/  and  /sponsor/promoted/:sort
# ---------------------------------------------------------------------------

@router.get("/sponsor/promoted/")
async def GET_sponsor_promoted_index(request: Request):
    from r2.controllers.promotecontroller import SponsorListingController
    return _to_response(
        await _call(SponsorListingController().GET_listing(sort='all')), request)


@router.get("/sponsor/promoted/{sort}")
async def GET_sponsor_promoted_sort(sort: str, request: Request):
    from r2.controllers.promotecontroller import SponsorListingController
    return _to_response(
        await _call(SponsorListingController().GET_listing(sort=sort)), request)


# ---------------------------------------------------------------------------
# SponsorListingController — /sponsor  (top-level sponsor listing)
# ---------------------------------------------------------------------------

@router.get("/sponsor")
@router.get("/sponsor/")
async def GET_sponsor_index(request: Request):
    from r2.controllers.promotecontroller import SponsorListingController
    return _to_response(
        await _call(SponsorListingController().GET_listing(sort='all')), request)
