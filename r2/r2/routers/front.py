"""
Native FastAPI router for FrontController, FormsController, and shared
namespace routes — Phase D-3 step 3h.

Strategy: same delegation pattern as listing.py — each handler instantiates
the appropriate controller class and delegates to its method.  Path params
flow into the @validate env dict via kwargs.

Namespaces now fully owned by this router:
  /login /register /logout /verify /adminon /adminoff /password
  /resetpassword /verification /mail/* /prefs/*
  /gold/* /gilding /thanks /try /creddits
  /submit
  /subreddits/* /reddits/*
  /awards/*
  /about/*  (subreddit-scoped and global; redirects for /about/values etc.)
  /search
  /comments/{article}/...  (comment thread page — distinct from /comments listing)
  /related /details /duplicates
  /random /explore /stylesheet /share/close /c/ /account-activity /contact
  /traffic/* /tb/ /info/ /modify_hsts_grant

Namespaces NOT yet migrated (left for later steps 3i/3j):
  /api/*  /post/* /promoted/* /sponsor/* /admin/* /dev/*
  /captcha /oembed /mediaembed /robots.txt /crossdomain /gtm
  /goto /tb/* (toolbar) /s/* (toolbar)
  /{link_id}  (short-link regex catch-all)
  /*url  (global catch-all → misc router's /{url:path} handler, D-4)
"""

import inspect

from fastapi import APIRouter, Request
from starlette.responses import Response, RedirectResponse
from starlette.exceptions import HTTPException

router = APIRouter()

_ABOUT_BASE = "https://about.reddit.com/"


# ---------------------------------------------------------------------------
# Helpers (identical to listing.py — kept local to avoid shared-state issues)
# ---------------------------------------------------------------------------

async def _call(coro_or_val):
    """Await a value if it is a coroutine."""
    if inspect.isawaitable(coro_or_val):
        return await coro_or_val
    return coro_or_val


def _to_response(result, request: Request) -> Response:
    """Convert a controller return value to a Starlette Response."""
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
# Account / auth forms
# ---------------------------------------------------------------------------

@router.get("/login")
@router.get("/subreddits/login")
@router.get("/reddits/login")
async def GET_login(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_login()), request)


@router.get("/register")
async def GET_register(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_register()), request)


@router.get("/logout")
async def GET_logout(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_logout()), request)


@router.post("/logout")
async def POST_logout(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().POST_logout()), request)


@router.get("/verify")
async def GET_verify(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_verify()), request)


@router.get("/adminon")
async def GET_adminon(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_adminon()), request)


@router.get("/adminoff")
async def GET_adminoff(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_adminoff()), request)


@router.get("/password")
async def GET_password(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_password()), request)


@router.get("/resetpassword")
async def GET_resetpassword(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_resetpassword()), request)


@router.get("/resetpassword/{key}")
async def GET_resetpassword_key(key: str, request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_resetpassword(key=key)), request)


@router.get("/verification/{key}")
async def GET_verify_email(key: str, request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_verify_email(key=key)), request)


# ---------------------------------------------------------------------------
# Mail opt-in / opt-out / unsubscribe
# ---------------------------------------------------------------------------

@router.get("/mail/optout")
async def GET_optout(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_optout()), request)


@router.get("/mail/optin")
async def GET_optin(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_optin()), request)


@router.get("/mail/unsubscribe/{user}/{key}")
async def GET_unsubscribe_emails(user: str, key: str, request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_unsubscribe_emails(
            user=user, key=key)),
        request)


# ---------------------------------------------------------------------------
# Prefs
#
# /prefs/friends and /prefs/blocked → UserListListingController.GET_user_prefs
# all other /prefs/{location}       → FormsController.GET_prefs
# ---------------------------------------------------------------------------

_USER_PREF_WHERES = {'friends', 'blocked'}


@router.get("/prefs/{where}")
async def GET_prefs(where: str, request: Request):
    if where in _USER_PREF_WHERES:
        from r2.controllers.listingcontroller import UserListListingController
        return _to_response(
            await _call(UserListListingController().GET_user_prefs(where=where)),
            request)
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_prefs(location=where)), request)


# ---------------------------------------------------------------------------
# Gold / gilding / creddits
#
# Specific /gold/* sub-paths registered BEFORE the bare /gold catch-all.
# ---------------------------------------------------------------------------

@router.get("/gold/thanks")
async def GET_goldthanks(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_goldthanks()), request)


@router.get("/gold/payment")
async def GET_gold_payment(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_gold(is_payment=True)), request)


@router.get("/gold/creditgild/{passthrough}")
async def GET_creditgild(passthrough: str, request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_creditgild(passthrough=passthrough)),
        request)


@router.get("/gold/subscription")
async def GET_subscription(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_subscription()), request)


@router.get("/gold")
async def GET_gold(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_gold(is_payment=False)), request)


@router.get("/gilding")
async def GET_gilding(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_gilding()), request)


# ---------------------------------------------------------------------------
# Thanks / award claim
# ---------------------------------------------------------------------------

@router.get("/thanks")
async def GET_thanks(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_claim(secret='')), request)


@router.get("/thanks/{secret}")
async def GET_thanks_secret(secret: str, request: Request):
    from r2.controllers.front import FormsController
    return _to_response(
        await _call(FormsController().GET_claim(secret=secret)), request)


# ---------------------------------------------------------------------------
# Try compact
# ---------------------------------------------------------------------------

@router.get("/try")
async def GET_try_compact(request: Request):
    from r2.controllers.front import FormsController
    return _to_response(await _call(FormsController().GET_try_compact()), request)


# ---------------------------------------------------------------------------
# Submit form
# (Multi-prefix /user/{u}/m/{mp}/submit and /me/m/{mp}/submit are registered
#  in listing.py before the /{sort} handler so ordering is correct.)
# ---------------------------------------------------------------------------

@router.get("/submit")
async def GET_submit(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_submit()), request)


# ---------------------------------------------------------------------------
# Subreddits / reddits namespace
#
# Literal paths (create, search, login) before mine/{where} before {where}.
# not_in_sr condition enforced inline for listing routes.
# ---------------------------------------------------------------------------

@router.get("/subreddits/create")
@router.get("/reddits/create")
async def GET_newreddit(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_newreddit()), request)


@router.get("/subreddits/search")
@router.get("/reddits/search")
async def GET_search_reddits(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_search_reddits()), request)


@router.get("/subreddits/mine/{where}")
@router.get("/reddits/mine/{where}")
async def GET_subreddits_mine(where: str, request: Request):
    if hasattr(request.state, 'subreddit'):
        raise HTTPException(status_code=404)
    from r2.controllers.listingcontroller import MyredditsController
    return _to_response(
        await _call(MyredditsController().GET_listing(where=where)), request)


@router.get("/subreddits/{where}")
@router.get("/reddits/{where}")
async def GET_subreddits_where(where: str, request: Request):
    if hasattr(request.state, 'subreddit'):
        raise HTTPException(status_code=404)
    from r2.controllers.listingcontroller import RedditsController
    return _to_response(
        await _call(RedditsController().GET_listing(where=where)), request)


# ---------------------------------------------------------------------------
# Traffic
#
# Three-segment literal paths registered before the two-segment catch-all.
# ---------------------------------------------------------------------------

@router.get("/traffic/subreddits/report")
async def GET_subreddit_traffic_report(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_subreddit_traffic_report()), request)


@router.get("/traffic/languages/{langcode}")
async def GET_lang_traffic(langcode: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_lang_traffic(langcode=langcode)), request)


@router.get("/traffic/adverts/{code}")
async def GET_advert_traffic(code: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_advert_traffic(code=code)), request)


@router.get("/traffic")
async def GET_site_traffic(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_site_traffic()), request)


@router.get("/traffic/{link}")
@router.get("/traffic/{link}/{campaign}")
async def GET_traffic(link: str, campaign: str = None, request: Request = None):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_traffic(link=link, campaign=campaign)),
        request)


# ---------------------------------------------------------------------------
# Awards
#
# Specific sub-paths before the bare /awards listing.
# ---------------------------------------------------------------------------

@router.get("/awards/received")
async def GET_received_award(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_received_award()), request)


@router.get("/awards/confirm/{code}")
async def GET_confirm_award_claim(code: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_confirm_award_claim(code=code)), request)


@router.post("/awards/claim/{code}")
async def POST_claim_award(code: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().POST_claim_award(code=code)), request)


@router.get("/awards")
async def GET_awards(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_awards()), request)


# ---------------------------------------------------------------------------
# About namespace
#
# Ordering (most specific first):
#   /about/values /about/team          → redirect to about.reddit.com
#   /about/alien                       → redirect to about.reddit.com/press
#   /about/message/{where}             → MessageController (literal "message")
#   /about/rules /about/sidebar /about/sticky /about/flair /about/log
#   /about/{location}                  → spamlisting | userlist | editreddit
#   /about                             → GET_about (in SR) or redirect
# ---------------------------------------------------------------------------

@router.get("/about/values")
@router.get("/about/team")
async def GET_about_reddit_pages(request: Request):
    return RedirectResponse(url=_ABOUT_BASE, status_code=301)


@router.get("/about/alien")
async def GET_about_alien(request: Request):
    return RedirectResponse(url=_ABOUT_BASE + "press", status_code=301)


@router.get("/about/message/{where}")
async def GET_about_message(where: str, request: Request):
    """Subreddit-scoped modmail listing (global /message/* is in listing.py)."""
    from r2.controllers.listingcontroller import MessageController
    return _to_response(
        await _call(MessageController().GET_listing(where=where)), request)


@router.get("/about/rules")
async def GET_about_rules(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_rules()), request)


@router.get("/about/sidebar")
async def GET_about_sidebar(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_sidebar()), request)


@router.get("/about/sticky")
async def GET_about_sticky(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_sticky()), request)


@router.get("/about/flair")
async def GET_about_flair(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_flairlisting()), request)


@router.get("/about/log")
async def GET_about_log(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_moderationlog()), request)


_SPAMLISTING_LOCATIONS = {'reports', 'spam', 'modqueue', 'unmoderated', 'edited'}
_USERLIST_LOCATIONS = {
    'contributors', 'banned', 'muted',
    'wikibanned', 'wikicontributors', 'moderators',
}
_EDITREDDIT_LOCATIONS = {'edit', 'stylesheet', 'traffic', 'about'}


@router.get("/about/{location}")
async def GET_about_location(location: str, request: Request):
    """Dispatch /about/{location} to the appropriate controller."""
    if location in _SPAMLISTING_LOCATIONS:
        from r2.controllers.front import FrontController
        return _to_response(
            await _call(FrontController().GET_spamlisting(location=location)),
            request)
    if location in _USERLIST_LOCATIONS:
        from r2.controllers.listingcontroller import UserListListingController
        return _to_response(
            await _call(UserListListingController().GET_listing(where=location)),
            request)
    if location in _EDITREDDIT_LOCATIONS:
        from r2.controllers.front import FrontController
        return _to_response(
            await _call(FrontController().GET_editreddit(location=location)),
            request)
    raise HTTPException(status_code=404)


@router.get("/about")
async def GET_about(request: Request):
    """
    Global /about → redirect to about.reddit.com (not_in_sr condition).
    Subreddit /r/{sr}/about → FrontController.GET_about (subreddit info page).
    """
    if not hasattr(request.state, 'subreddit'):
        return RedirectResponse(url=_ABOUT_BASE, status_code=301)
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_about()), request)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@router.get("/search")
async def GET_search(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_search()), request)


# ---------------------------------------------------------------------------
# Comment thread page — /comments/{article}/...
#
# Distinct from the listing router's /comments (no article param).
# The listing router is included first so /comments/gilded still routes to
# GildedController; /comments/{anything_else} lands here.
# ---------------------------------------------------------------------------

@router.get("/comments/{article}")
@router.get("/comments/{article}/{title}")
@router.get("/comments/{article}/{title}/{comment}")
async def GET_comments_article(article: str, title: str = None,
                                comment: str = None, request: Request = None):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_comments(
            article=article, title=title, comment=comment)),
        request)


# ---------------------------------------------------------------------------
# Related / duplicates / details
# (title param is optional in routing.py — handled via multiple route defs)
# ---------------------------------------------------------------------------

@router.get("/related/{article}")
@router.get("/related/{article}/{title}")
async def GET_related(article: str, title: str = None, request: Request = None):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_related(article=article, title=title)),
        request)


@router.get("/details/{article}")
@router.get("/details/{article}/{title}")
async def GET_details(article: str, title: str = None, request: Request = None):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_details(article=article, title=title)),
        request)


@router.get("/duplicates/{article}")
@router.get("/duplicates/{article}/{title}")
async def GET_duplicates(article: str, title: str = None, request: Request = None):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_duplicates(
            article=article, title=title)),
        request)


# ---------------------------------------------------------------------------
# Miscellaneous front page handlers
# ---------------------------------------------------------------------------

@router.get("/random")
async def GET_random(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_random()), request)


@router.get("/explore")
async def GET_explore(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_explore()), request)


@router.get("/stylesheet")
async def GET_stylesheet(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_stylesheet()), request)


@router.get("/share/close")
async def GET_share_close(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_share_close()), request)


@router.get("/c/{comment_id}")
async def GET_comment_by_id(comment_id: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_comment_by_id(comment_id=comment_id)),
        request)


@router.get("/account-activity")
async def GET_account_activity(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(await _call(FrontController().GET_account_activity()), request)


@router.get("/contact")
async def GET_contact_us(request: Request):
    from r2.controllers.front import FrontUnstyledController
    return _to_response(
        await _call(FrontUnstyledController().GET_contact_us()), request)


# ---------------------------------------------------------------------------
# Link-ID redirect via /tb/ prefix
# (The bare /{link_id} regex route stays in the legacy dispatcher for now.)
# ---------------------------------------------------------------------------

@router.get("/tb/{link_id}")
async def GET_tb_link_id_redirect(link_id: str, request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController().GET_link_id_redirect(link_id=link_id)),
        request)


# ---------------------------------------------------------------------------
# Legacy info redirect — /info/0{article}/{rest} and /info/{article}/{dest}/{comment}
# ---------------------------------------------------------------------------

@router.get("/info/{path:path}")
async def GET_oldinfo(path: str, request: Request):
    from r2.controllers.front import FrontController
    parts = path.strip('/').split('/')
    seg0 = parts[0] if parts else ''
    if seg0.startswith('0'):
        # type='ancient': /info/0{article}/{rest} — strip the leading '0'
        article = seg0[1:]
        rest = '/'.join(parts[1:]) if len(parts) > 1 else ''
        return _to_response(
            await _call(FrontController().GET_oldinfo(
                article=article, dest='comments', type='ancient', rest=rest)),
            request)
    # type='old': /info/{article}/{dest}/{comment}
    article = seg0
    dest = parts[1] if len(parts) > 1 else 'comments'
    comment = parts[2] if len(parts) > 2 else None
    return _to_response(
        await _call(FrontController().GET_oldinfo(
            article=article, dest=dest, comment=comment, type='old')),
        request)


# ---------------------------------------------------------------------------
# HSTS grant — responds to all HTTP methods (GET/POST/PUT/DELETE)
# ---------------------------------------------------------------------------

@router.get("/modify_hsts_grant")
@router.post("/modify_hsts_grant")
@router.put("/modify_hsts_grant")
@router.delete("/modify_hsts_grant")
async def ANY_modify_hsts_grant(request: Request):
    from r2.controllers.front import FrontController
    return _to_response(
        await _call(FrontController()._modify_hsts_grant()), request)
