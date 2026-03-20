"""
Native FastAPI router for payment / IPN endpoints — Phase D-3 step 3j.

Controllers covered:
  IpnController           (ipn.py) — /api/spendcreddits, /api/ipn/:secret, /ipn/:secret
  StripeController        (ipn.py) — /api/stripecharge/gold, /api/stripewebhook/gold/:secret,
                                     /api/modify_subscription, /api/cancel_subscription
  CoinbaseController      (ipn.py) — /api/coinbasewebhook/gold/:secret
  RedditGiftsController   (ipn.py) — /api/rgwebhook/gold/:secret

All routes are POST-only (payment callbacks and user-facing payment actions).

Route ordering: specific literal paths before parameterised ones.
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
# IpnController — /api/spendcreddits
# ---------------------------------------------------------------------------

@router.post("/api/spendcreddits")
async def POST_spendcreddits(request: Request):
    from r2.controllers.ipn import IpnController
    return _to_response(
        await _call(IpnController().POST_spendcreddits()), request)


# ---------------------------------------------------------------------------
# StripeController — /api/stripecharge/gold, /api/stripewebhook/gold/:secret,
#                    /api/modify_subscription, /api/cancel_subscription
# (registered before /api/ipn/:secret to avoid false matches on /api/*)
# ---------------------------------------------------------------------------

@router.post("/api/stripecharge/gold")
async def POST_goldcharge(request: Request):
    from r2.controllers.ipn import StripeController
    return _to_response(
        await _call(StripeController().POST_goldcharge()), request)


@router.post("/api/stripewebhook/gold/{secret}")
async def POST_stripe_webhook(secret: str, request: Request):
    from r2.controllers.ipn import StripeController
    return _to_response(
        await _call(StripeController().POST_goldwebhook(secret=secret)), request)


@router.post("/api/modify_subscription")
async def POST_modify_subscription(request: Request):
    from r2.controllers.ipn import StripeController
    return _to_response(
        await _call(StripeController().POST_modify_subscription()), request)


@router.post("/api/cancel_subscription")
async def POST_cancel_subscription(request: Request):
    from r2.controllers.ipn import StripeController
    return _to_response(
        await _call(StripeController().POST_cancel_subscription()), request)


# ---------------------------------------------------------------------------
# CoinbaseController — /api/coinbasewebhook/gold/:secret
# ---------------------------------------------------------------------------

@router.post("/api/coinbasewebhook/gold/{secret}")
async def POST_coinbase_webhook(secret: str, request: Request):
    from r2.controllers.ipn import CoinbaseController
    return _to_response(
        await _call(CoinbaseController().POST_goldwebhook(secret=secret)), request)


# ---------------------------------------------------------------------------
# RedditGiftsController — /api/rgwebhook/gold/:secret
# ---------------------------------------------------------------------------

@router.post("/api/rgwebhook/gold/{secret}")
async def POST_rg_webhook(secret: str, request: Request):
    from r2.controllers.ipn import RedditGiftsController
    return _to_response(
        await _call(RedditGiftsController().POST_goldwebhook(secret=secret)), request)


# ---------------------------------------------------------------------------
# IpnController — /api/ipn/:secret  and  /ipn/:secret
# ---------------------------------------------------------------------------

@router.post("/api/ipn/{secret}")
async def POST_api_ipn(secret: str, request: Request):
    from r2.controllers.ipn import IpnController
    return _to_response(
        await _call(IpnController().POST_ipn(paypal_secret=secret)), request)


@router.post("/ipn/{secret}")
async def POST_ipn(secret: str, request: Request):
    from r2.controllers.ipn import IpnController
    return _to_response(
        await _call(IpnController().POST_ipn(paypal_secret=secret)), request)
