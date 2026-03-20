"""
Native FastAPI router for all remaining small controllers — Phase D-3 step 3j.

Controllers covered:
  PostController           (post.py)              — /over18, /quarantine, /post/*
  ToolbarController        (toolbar.py)            — /goto, /toolbar/*, /s/*
  RedirectController       (redirect.py)           — /u/*, /t/*, fixed-dest redirects
  RobotsController         (robots.py)             — /robots.txt, /crossdomain
  WebLogController         (web.py)                — /web/log/:level, /web/poisoning
  CaptchaController        (captcha.py)            — /captcha/:iden
  OEmbedController         (oembed.py)             — /oembed
  NewsletterController     (newsletter.py)         — /newsletter
  GoogleTagManagerController (googletagmanager.py) — /gtm/jail, /gtm
  MediaembedController     (mediaembed.py)         — /mediaembed/:link/:credentials
  AdController             (mediaembed.py)         — /ads/
  PoliciesController       (policies.py)           — /help/:page  (not_in_sr)
  AwardsController         (awards.py)             — /admin/, /admin/awards, /admin/awards/:cn/:action
  AdminToolController      (admin.py)              — /admin/creddits, /admin/gold
  ApidocsController        (api_docs.py)           — /dev/api, /dev/api/:mode

Excluded (remain in legacy dispatcher until D-4):
  /{link_id}    — regex catch-all [0-9a-z]{1,6}
  /{urloid}     — URL catch-all (\w+\.\w{2,}|https?).*
  /*url         — global catch-all → FrontController.GET_catchall

Route ordering notes:
  - /help/gold (redirect) BEFORE /help/{page} (policies)
  - /admin/creddits and /admin/gold (admin tool) BEFORE /admin/awards/{cn}/{action}
  - /admin/ and /admin/awards (literal) BEFORE /admin/{...} parameterised routes
  - /gtm/jail (literal) BEFORE /gtm (shorter literal)
  - /post/{action}/{url_user} (3-seg) BEFORE /post/{action} (2-seg) — but FastAPI
    matches by depth naturally; still register 3-seg first to be explicit.
"""

import inspect

from fastapi import APIRouter, Request
from starlette.responses import Response, RedirectResponse
from starlette.exceptions import HTTPException

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
# PostController — /over18 and /quarantine interstitials
# ---------------------------------------------------------------------------

@router.get("/over18")
async def GET_over18(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().GET_over18()), request)


@router.post("/over18")
async def POST_over18(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_over18()), request)


@router.get("/quarantine")
async def GET_quarantine(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().GET_quarantine()), request)


@router.post("/quarantine")
async def POST_quarantine(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_quarantine()), request)


# ---------------------------------------------------------------------------
# PostController — /post/:action/:url_user  (login/reg with username in path)
# Must be registered before /post/{action} (same-depth parameterised).
# ---------------------------------------------------------------------------

@router.post("/post/login/{url_user}")
async def POST_post_login_user(url_user: str, request: Request):
    from r2.controllers.post import PostController
    return _to_response(
        await _call(PostController().POST_login(url_user=url_user)), request)


@router.post("/post/reg/{url_user}")
async def POST_post_reg_user(url_user: str, request: Request):
    from r2.controllers.post import PostController
    return _to_response(
        await _call(PostController().POST_reg(url_user=url_user)), request)


# ---------------------------------------------------------------------------
# PostController — /post/:action  (generic form POST dispatcher)
# action ∈ {options, over18, unlogged_options, optout, optin, login, reg,
#            explore_settings}
# ---------------------------------------------------------------------------

@router.get("/post/login")
async def GET_post_login(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().GET_login()), request)


@router.post("/post/options")
async def POST_options(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_options()), request)


@router.post("/post/unlogged_options")
async def POST_unlogged_options(request: Request):
    from r2.controllers.post import PostController
    return _to_response(
        await _call(PostController().POST_unlogged_options()), request)


@router.post("/post/optout")
async def POST_post_optout(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_optout()), request)


@router.post("/post/optin")
async def POST_post_optin(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_optin()), request)


@router.post("/post/login")
async def POST_post_login(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_login()), request)


@router.post("/post/reg")
async def POST_post_reg(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_reg()), request)


@router.post("/post/over18")
async def POST_post_over18(request: Request):
    from r2.controllers.post import PostController
    return _to_response(await _call(PostController().POST_over18()), request)


@router.post("/post/explore_settings")
async def POST_explore_settings(request: Request):
    from r2.controllers.post import PostController
    return _to_response(
        await _call(PostController().POST_explore_settings()), request)


# ---------------------------------------------------------------------------
# ToolbarController — /goto, /toolbar/*, /s/*
# ---------------------------------------------------------------------------

@router.get("/goto")
async def GET_goto(request: Request):
    from r2.controllers.toolbar import ToolbarController
    return _to_response(await _call(ToolbarController().GET_goto()), request)


@router.get("/toolbar/{frame:path}")
async def GET_toolbar_redirect(frame: str, request: Request):
    from r2.controllers.toolbar import ToolbarController
    return _to_response(await _call(ToolbarController().GET_redirect()), request)


@router.get("/s/{urloid:path}")
async def GET_toolbar_s(urloid: str, request: Request):
    from r2.controllers.toolbar import ToolbarController
    return _to_response(
        await _call(ToolbarController().GET_s(urloid=urloid)), request)


# ---------------------------------------------------------------------------
# RedirectController — /u/:username  and  /t/:timereddit
# ---------------------------------------------------------------------------

@router.get("/u/{username}")
async def GET_user_redirect(username: str, request: Request):
    from r2.controllers.redirect import RedirectController
    return _to_response(
        await _call(RedirectController().GET_user_redirect(username=username)),
        request)


@router.get("/u/{username}/{rest:path}")
async def GET_user_redirect_rest(username: str, rest: str, request: Request):
    from r2.controllers.redirect import RedirectController
    return _to_response(
        await _call(RedirectController().GET_user_redirect(
            username=username, rest=rest)),
        request)


@router.get("/t/{timereddit}")
async def GET_timereddit_redirect(timereddit: str, request: Request):
    from r2.controllers.redirect import RedirectController
    return _to_response(
        await _call(RedirectController().GET_timereddit_redirect(
            timereddit=timereddit)),
        request)


@router.get("/t/{timereddit}/{rest:path}")
async def GET_timereddit_redirect_rest(timereddit: str, rest: str,
                                       request: Request):
    from r2.controllers.redirect import RedirectController
    return _to_response(
        await _call(RedirectController().GET_timereddit_redirect(
            timereddit=timereddit, rest=rest)),
        request)


# ---------------------------------------------------------------------------
# Fixed-destination redirects — simple 301/302 with hardcoded dest
# ---------------------------------------------------------------------------

@router.get("/r")
async def GET_r_redirect(request: Request):
    return RedirectResponse(url='/subreddits', status_code=301)


@router.get("/api")
async def GET_api_redirect(request: Request):
    return RedirectResponse(url='/dev/api', status_code=301)


@router.get("/creddits")
async def GET_creddits_redirect(request: Request):
    return RedirectResponse(url='/gold?goldtype=creddits', status_code=301)


@router.get("/rules")
async def GET_rules_redirect(request: Request):
    return RedirectResponse(url='/help/contentpolicy', status_code=301)


@router.get("/faq")
async def GET_faq_redirect(request: Request):
    return RedirectResponse(url='https://reddit.zendesk.com/', status_code=301)


@router.get("/code")
async def GET_code_redirect(request: Request):
    return RedirectResponse(url='http://github.com/theorangedit/', status_code=301)


@router.get("/socialite")
async def GET_socialite_redirect(request: Request):
    return RedirectResponse(
        url='https://addons.mozilla.org/firefox/addon/socialite/', status_code=301)


@router.get("/i18n")
async def GET_i18n_redirect(request: Request):
    return RedirectResponse(
        url='http://www.reddit.com/r/i18n', status_code=301)


@router.get("/feedback")
async def GET_feedback_redirect(request: Request):
    return RedirectResponse(
        url='http://www.reddit.com/r/feedback', status_code=301)


@router.get("/jobs")
async def GET_jobs_redirect(request: Request):
    return RedirectResponse(
        url='http://www.reddit.com/r/jobs', status_code=301)


@router.get("/dev")
async def GET_dev_redirect(request: Request):
    return RedirectResponse(url='/dev/api', status_code=301)


# ---------------------------------------------------------------------------
# RobotsController — /robots.txt  and  /crossdomain
# ---------------------------------------------------------------------------

@router.get("/robots.txt")
async def GET_robots(request: Request):
    from r2.controllers.robots import RobotsController
    return _to_response(await _call(RobotsController().GET_robots()), request)


@router.get("/crossdomain")
async def GET_crossdomain(request: Request):
    from r2.controllers.robots import RobotsController
    return _to_response(
        await _call(RobotsController().GET_crossdomain()), request)


# ---------------------------------------------------------------------------
# WebLogController — /web/log/:level  and  /web/poisoning
# (/web/timings has no handler — omitted)
# ---------------------------------------------------------------------------

@router.post("/web/log/{level}")
async def POST_web_log(level: str, request: Request):
    from r2.controllers.web import WebLogController
    return _to_response(
        await _call(WebLogController().POST_message(level=level)), request)


@router.post("/web/poisoning")
async def POST_web_poisoning(request: Request):
    from r2.controllers.web import WebLogController
    return _to_response(
        await _call(WebLogController().POST_report_cache_poisoning()), request)


# ---------------------------------------------------------------------------
# CaptchaController — /captcha/:iden
# ---------------------------------------------------------------------------

@router.get("/captcha/{iden}")
async def GET_captcha(iden: str, request: Request):
    from r2.controllers.captcha import CaptchaController
    return _to_response(
        await _call(CaptchaController().GET_captchaimg(iden=iden)), request)


# ---------------------------------------------------------------------------
# OEmbedController — /oembed
# ---------------------------------------------------------------------------

@router.get("/oembed")
async def GET_oembed(request: Request):
    from r2.controllers.oembed import OEmbedController
    return _to_response(await _call(OEmbedController().GET_oembed()), request)


# ---------------------------------------------------------------------------
# NewsletterController — /newsletter
# ---------------------------------------------------------------------------

@router.get("/newsletter")
async def GET_newsletter(request: Request):
    from r2.controllers.newsletter import NewsletterController
    return _to_response(
        await _call(NewsletterController().GET_newsletter()), request)


# ---------------------------------------------------------------------------
# GoogleTagManagerController — /gtm/jail  (before /gtm)  and  /gtm
# ---------------------------------------------------------------------------

@router.get("/gtm/jail")
async def GET_gtm_jail(request: Request):
    from r2.controllers.googletagmanager import GoogleTagManagerController
    return _to_response(
        await _call(GoogleTagManagerController().GET_jail()), request)


@router.get("/gtm")
async def GET_gtm(request: Request):
    from r2.controllers.googletagmanager import GoogleTagManagerController
    return _to_response(
        await _call(GoogleTagManagerController().GET_gtm()), request)


# ---------------------------------------------------------------------------
# MediaembedController — /mediaembed/:link/:credentials
# AdController         — /ads/
# ---------------------------------------------------------------------------

@router.get("/mediaembed/{link}/{credentials}")
async def GET_mediaembed(link: str, credentials: str, request: Request):
    from r2.controllers.mediaembed import MediaembedController
    return _to_response(
        await _call(MediaembedController().GET_mediaembed(
            link=link, credentials=credentials)),
        request)


@router.get("/mediaembed/{link}")
async def GET_mediaembed_no_creds(link: str, request: Request):
    from r2.controllers.mediaembed import MediaembedController
    return _to_response(
        await _call(MediaembedController().GET_mediaembed(
            link=link, credentials=None)),
        request)


@router.get("/ads/")
async def GET_ad(request: Request):
    from r2.controllers.mediaembed import AdController
    return _to_response(await _call(AdController().GET_ad()), request)


# ---------------------------------------------------------------------------
# ApidocsController — /dev/api  and  /dev/api/:mode
# (/dev is a simple redirect handled above)
# ---------------------------------------------------------------------------

@router.get("/dev/api")
async def GET_dev_api(request: Request):
    from r2.controllers.api_docs import ApidocsController
    return _to_response(
        await _call(ApidocsController().GET_docs()), request)


@router.get("/dev/api/{mode}")
async def GET_dev_api_mode(mode: str, request: Request):
    from r2.controllers.api_docs import ApidocsController
    return _to_response(
        await _call(ApidocsController().GET_docs(mode=mode)), request)


# ---------------------------------------------------------------------------
# PoliciesController — /help/gold redirect (BEFORE /help/:page)
#                      /help/:page  (not_in_sr: only outside subreddit context)
# ---------------------------------------------------------------------------

@router.get("/help/gold")
async def GET_help_gold_redirect(request: Request):
    return RedirectResponse(url='/gold/about', status_code=301)


@router.get("/help/{page}")
async def GET_help_page(page: str, request: Request):
    if hasattr(request.state, 'subreddit'):
        raise HTTPException(status_code=404)
    from r2.controllers.policies import PoliciesController
    return _to_response(
        await _call(PoliciesController().GET_policy_page(page=page)), request)


# ---------------------------------------------------------------------------
# AdminToolController — /admin/creddits  and  /admin/gold
# (registered before /admin/awards/*, and before /admin/ to avoid conflicts)
# ---------------------------------------------------------------------------

@router.get("/admin/creddits")
async def GET_admin_creddits(request: Request):
    from r2.controllers.admin import AdminToolController
    return _to_response(
        await _call(AdminToolController().GET_creddits()), request)


@router.get("/admin/gold")
async def GET_admin_gold(request: Request):
    from r2.controllers.admin import AdminToolController
    return _to_response(
        await _call(AdminToolController().GET_gold()), request)


# ---------------------------------------------------------------------------
# AwardsController — /admin/  /admin/awards  /admin/awards/:awardcn/:action
# ---------------------------------------------------------------------------

@router.get("/admin/awards/{awardcn}/give")
async def GET_award_give(awardcn: str, request: Request):
    from r2.controllers.awards import AwardsController
    return _to_response(
        await _call(AwardsController().GET_give(awardcn=awardcn)), request)


@router.get("/admin/awards/{awardcn}/winners")
async def GET_award_winners(awardcn: str, request: Request):
    from r2.controllers.awards import AwardsController
    return _to_response(
        await _call(AwardsController().GET_winners(awardcn=awardcn)), request)


@router.get("/admin/awards")
async def GET_admin_awards(request: Request):
    from r2.controllers.awards import AwardsController
    return _to_response(await _call(AwardsController().GET_index()), request)


@router.get("/admin/")
@router.get("/admin")
async def GET_admin_index(request: Request):
    from r2.controllers.awards import AwardsController
    return _to_response(await _call(AwardsController().GET_index()), request)


# ---------------------------------------------------------------------------
# Root-level catch-alls — must be LAST in this router (and misc is last in
# main.py) so they only fire when no other route has matched.
#
# /{link_id}  — short alphanumeric IDs [0-9a-z]{1,6} → link_id_redirect
# /{urloid}   — URL-like patterns pasted into the address bar → toolbar /s/
# /{url:path} — global catch-all → FrontController.GET_catchall
#
# /{link_id} and /{urloid} share the same path depth (single root segment).
# They are combined into one handler with internal regex dispatch.
# ---------------------------------------------------------------------------

import re as _re

_LINK_ID_RE = _re.compile(r'^[0-9a-z]{1,6}$')
_URLOID_RE = _re.compile(r'^(\w+\.\w{2,}|https?).*$')


@router.get("/{link_id}")
async def GET_root_single(link_id: str, request: Request):
    """Single-segment root catch-all: link IDs and URL-like strings."""
    if _LINK_ID_RE.match(link_id):
        from r2.controllers.front import FrontController
        return _to_response(
            await _call(FrontController().GET_link_id_redirect(link_id=link_id)),
            request)
    if _URLOID_RE.match(link_id):
        from r2.controllers.toolbar import ToolbarController
        return _to_response(
            await _call(ToolbarController().GET_s(urloid=link_id)), request)
    # Nothing matched — defer to catchall
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_catchall()), request)


@router.api_route("/{url:path}", methods=["GET", "POST", "PUT", "DELETE",
                                           "PATCH", "HEAD"])
async def GET_catchall(url: str, request: Request):
    """Global catch-all for all other unmatched paths."""
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_catchall()), request)
