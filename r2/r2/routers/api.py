"""
Native FastAPI router for ApiController, ApiminimalController, and the
PromoteApiController /api/* actions — Phase D-3 step 3i.

All routes follow the delegation pattern: instantiate the controller class
and call its method, with path params passed as kwargs into the @validate env.

Controllers covered:
  ApiminimalController  (api.py)   — /api/new_captcha
  PromoteApiController  (promotecontroller.py) — /api/promote, /api/edit_campaign, …
  ApiController         (api.py)   — everything else under /api/*
  MailgunWebhookController  (mailgun.py) — /api/zendeskreply only

Left for step 3j (different controller files):
  IpnController / StripeController / CoinbaseController / RedditGiftsController
    → /api/spendcreddits, /api/stripecharge/*, /api/ipn/*, /ipn/*
  PostController → /over18, /quarantine, /post/*
  Other remaining controllers not in api.py / promotecontroller.py

Routing note: routes with path params or literal disambiguators (gadget/click,
distinguish/{how}, relnote synonyms) are registered BEFORE the generic
GET/POST /api/{standard_action} routes so specifics always win.
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
# /button_info  — non-/api/ alias for GET_url_info with limit=1
# /quarantine_optout — non-/api/ route handled by ApiController
# ---------------------------------------------------------------------------

@router.get("/button_info")
async def GET_button_info(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_url_info(limit=1)), request)


@router.post("/quarantine_optout")
async def POST_quarantine_optout(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_quarantine_optout()), request)


# ---------------------------------------------------------------------------
# ApiminimalController — POST /api/new_captcha
# ---------------------------------------------------------------------------

@router.post("/api/new_captcha")
async def POST_new_captcha(request: Request):
    from r2.controllers.api import ApiminimalController
    return _to_response(
        await _call(ApiminimalController().POST_new_captcha()), request)


# ---------------------------------------------------------------------------
# MailgunWebhookController — POST /api/zendeskreply
# ---------------------------------------------------------------------------

@router.post("/api/zendeskreply")
async def POST_zendeskreply(request: Request):
    from r2.controllers.mailgun import MailgunWebhookController
    return _to_response(
        await _call(MailgunWebhookController().POST_zendeskreply()), request)


# ---------------------------------------------------------------------------
# Special /api/ routes with path parameters or non-trivial URL structure
# (must be registered before the standard /api/{action} catch-alls below)
# ---------------------------------------------------------------------------

# POST /api/distinguish/{how}  — 'how' is also in POST body; path param flows
# into env dict so @validate picks it up as a fallback.
@router.post("/api/distinguish/{how}")
async def POST_distinguish_how(how: str, request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_distinguish(how=how)), request)


# POST /api/login/{url_user}  and  POST /api/register/{url_user}
@router.post("/api/login/{url_user}")
async def POST_login_url_user(url_user: str, request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_login(url_user=url_user)), request)


@router.post("/api/register/{url_user}")
async def POST_register_url_user(url_user: str, request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_register(url_user=url_user)), request)


# GET /api/gadget/click/{ids}  (literal 'click' before generic /{type})
@router.get("/api/gadget/click/{ids}")
async def GET_gadget_click(ids: str, request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_gadget(type='click', ids=ids)), request)


@router.get("/api/gadget/{type}")
async def GET_gadget_type(type: str, request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_gadget(type=type)), request)


# POST /api/{wikibannednote,bannednote,mutednote} → POST_relnote(type=...)
@router.post("/api/wikibannednote")
async def POST_wikibannednote(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_relnote(type='wikibannednote')), request)


@router.post("/api/bannednote")
async def POST_bannednote(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_relnote(type='bannednote')), request)


@router.post("/api/mutednote")
async def POST_mutednote(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_relnote(type='mutednote')), request)


# GET /api/recommend/sr/{srnames}
@router.get("/api/recommend/sr/{srnames}")
async def GET_subreddit_recommendations(srnames: str, request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_subreddit_recommendations(srnames=srnames)),
        request)


# POST /api/recommend/feedback
@router.post("/api/recommend/feedback")
async def POST_rec_feedback(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_rec_feedback()), request)


# ---------------------------------------------------------------------------
# PromoteApiController — /api/* advertising actions
# ---------------------------------------------------------------------------

@router.get("/api/check_inventory")
async def GET_check_inventory(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().GET_check_inventory()), request)


@router.get("/api/ad_s3_callback")
async def GET_ad_s3_callback(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().GET_ad_s3_callback()), request)


@router.post("/api/freebie")
async def POST_freebie(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_freebie()), request)


@router.post("/api/promote_note")
async def POST_promote_note(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_promote_note()), request)


@router.post("/api/review_fraud")
async def POST_review_fraud(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_review_fraud()), request)


@router.post("/api/promote")
async def POST_promote(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_promote()), request)


@router.post("/api/unpromote")
async def POST_unpromote(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_unpromote()), request)


@router.post("/api/refund_campaign")
async def POST_refund_campaign(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_refund_campaign()), request)


@router.post("/api/create_promo")
async def POST_create_promo(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_create_promo()), request)


@router.post("/api/edit_promo")
async def POST_edit_promo(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_edit_promo()), request)


@router.post("/api/edit_campaign")
async def POST_edit_campaign(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_edit_campaign()), request)


@router.post("/api/delete_campaign")
async def POST_delete_campaign(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_delete_campaign()), request)


@router.post("/api/toggle_pause_campaign")
async def POST_toggle_pause_campaign(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_toggle_pause_campaign()), request)


@router.post("/api/terminate_campaign")
async def POST_terminate_campaign(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_terminate_campaign()), request)


@router.post("/api/update_pay")
async def POST_update_pay(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_update_pay()), request)


@router.post("/api/ad_s3_params")
async def POST_ad_s3_params(request: Request):
    from r2.controllers.promotecontroller import PromoteApiController
    return _to_response(
        await _call(PromoteApiController().POST_ad_s3_params()), request)


# ---------------------------------------------------------------------------
# ApiController — GET methods
# ---------------------------------------------------------------------------

@router.get("/api/info")
async def GET_info(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_info()), request)


@router.get("/api/url_info")
async def GET_url_info(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_url_info()), request)


@router.get("/api/me")
async def GET_me(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_me()), request)


@router.get("/api/username_available")
async def GET_username_available(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_username_available()), request)


@router.get("/api/needs_captcha")
async def GET_needs_captcha(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_needs_captcha()), request)


@router.get("/api/saved_categories")
async def GET_saved_categories(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_saved_categories()), request)


@router.get("/api/expando")
async def GET_expando(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_expando()), request)


@router.get("/api/morechildren")
async def GET_morechildren(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_morechildren()), request)


@router.get("/api/flairlist")
async def GET_flairlist(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_flairlist()), request)


@router.get("/api/subreddits_by_topic")
async def GET_subreddits_by_topic(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_subreddits_by_topic()), request)


@router.get("/api/report_form")
async def GET_report_form(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_report_form()), request)


@router.get("/api/submit_text")
async def GET_submit_text(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().GET_submit_text()), request)


# ---------------------------------------------------------------------------
# ApiController — POST methods (alphabetical within each functional group)
# ---------------------------------------------------------------------------

# -- Auth / account --
@router.post("/api/login")
async def POST_login(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_login()), request)


@router.post("/api/register")
async def POST_register(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_register()), request)


@router.post("/api/check_username")
async def POST_check_username(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_check_username()), request)


@router.post("/api/check_password")
async def POST_check_password(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_check_password()), request)


@router.post("/api/check_email")
async def POST_check_email(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_check_email()), request)


@router.post("/api/newsletter")
async def POST_newsletter(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_newsletter()), request)


@router.post("/api/clear_sessions")
async def POST_clear_sessions(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_clear_sessions()), request)


@router.post("/api/update_email")
async def POST_update_email(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_update_email()), request)


@router.post("/api/update_password")
async def POST_update_password(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_update_password()), request)


@router.post("/api/deactivate_user")
async def POST_deactivate_user(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_deactivate_user()), request)


@router.post("/api/password")
async def POST_password(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_password()), request)


@router.post("/api/resetpassword")
async def POST_resetpassword(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_resetpassword()), request)


# -- OTP / admin --
@router.post("/api/adminon")
async def POST_adminon(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_adminon()), request)


@router.post("/api/generate_otp_secret")
async def POST_generate_otp_secret(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_generate_otp_secret()), request)


@router.post("/api/enable_otp")
async def POST_enable_otp(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_enable_otp()), request)


@router.post("/api/disable_otp")
async def POST_disable_otp(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_disable_otp()), request)


# -- Friends / relationships --
@router.post("/api/friend")
async def POST_friend(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_friend()), request)


@router.post("/api/unfriend")
async def POST_unfriend(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_unfriend()), request)


@router.post("/api/friendnote")
async def POST_friendnote(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_friendnote()), request)


@router.post("/api/relnote")
async def POST_relnote(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_relnote()), request)


@router.post("/api/block")
async def POST_block(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_block()), request)


@router.post("/api/unblock_subreddit")
async def POST_unblock_subreddit(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_unblock_subreddit()), request)


# -- Moderation / subreddit membership --
@router.post("/api/leavemoderator")
async def POST_leavemoderator(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_leavemoderator()), request)


@router.post("/api/leavecontributor")
async def POST_leavecontributor(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_leavecontributor()), request)


@router.post("/api/setpermissions")
async def POST_setpermissions(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_setpermissions()), request)


@router.post("/api/accept_moderator_invite")
async def POST_accept_moderator_invite(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_accept_moderator_invite()), request)


@router.post("/api/subscribe")
async def POST_subscribe(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_subscribe()), request)


# -- Submission / editing --
@router.post("/api/submit")
async def POST_submit(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_submit()), request)


@router.post("/api/compose")
async def POST_compose(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_compose()), request)


@router.post("/api/fetch_title")
async def POST_fetch_title(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_fetch_title()), request)


@router.post("/api/comment")
async def POST_comment(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_comment()), request)


@router.post("/api/editusertext")
async def POST_editusertext(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_editusertext()), request)


@router.post("/api/del")
async def POST_del(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_del()), request)


@router.post("/api/share")
async def POST_share(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_share()), request)


@router.post("/api/rescrape")
async def POST_rescrape(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_rescrape()), request)


# -- Voting / saving / hiding --
@router.post("/api/vote")
async def POST_vote(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_vote()), request)


@router.post("/api/save")
async def POST_save(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_save()), request)


@router.post("/api/unsave")
async def POST_unsave(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_unsave()), request)


@router.post("/api/hide")
async def POST_hide(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_hide()), request)


@router.post("/api/unhide")
async def POST_unhide(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_unhide()), request)


@router.post("/api/store_visits")
async def POST_store_visits(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_store_visits()), request)


# -- Post/comment state --
@router.post("/api/lock")
async def POST_lock(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_lock()), request)


@router.post("/api/unlock")
async def POST_unlock(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_unlock()), request)


@router.post("/api/marknsfw")
async def POST_marknsfw(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_marknsfw()), request)


@router.post("/api/unmarknsfw")
async def POST_unmarknsfw(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_unmarknsfw()), request)


@router.post("/api/sendreplies")
async def POST_sendreplies(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_sendreplies()), request)


@router.post("/api/set_suggested_sort")
async def POST_set_suggested_sort(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_set_suggested_sort()), request)


@router.post("/api/set_contest_mode")
async def POST_set_contest_mode(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_set_contest_mode()), request)


@router.post("/api/set_subreddit_sticky")
async def POST_set_subreddit_sticky(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_set_subreddit_sticky()), request)


@router.post("/api/distinguish")
async def POST_distinguish(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_distinguish()), request)


# -- Reports / moderation actions --
@router.post("/api/report")
async def POST_report(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_report()), request)


@router.post("/api/remove")
async def POST_remove(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_remove()), request)


@router.post("/api/approve")
async def POST_approve(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_approve()), request)


@router.post("/api/ignore_reports")
async def POST_ignore_reports(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_ignore_reports()), request)


@router.post("/api/unignore_reports")
async def POST_unignore_reports(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_unignore_reports()), request)


# -- Messages --
@router.post("/api/del_msg")
async def POST_del_msg(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_del_msg()), request)


@router.post("/api/collapse_message")
async def POST_collapse_message(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_collapse_message()), request)


@router.post("/api/uncollapse_message")
async def POST_uncollapse_message(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_uncollapse_message()), request)


@router.post("/api/unread_message")
async def POST_unread_message(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_unread_message()), request)


@router.post("/api/read_message")
async def POST_read_message(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_read_message()), request)


@router.post("/api/read_all_messages")
async def POST_read_all_messages(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_read_all_messages()), request)


@router.post("/api/mute_message_author")
async def POST_mute_message_author(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_mute_message_author()), request)


@router.post("/api/unmute_message_author")
async def POST_unmute_message_author(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_unmute_message_author()), request)


@router.post("/api/moremessages")
async def POST_moremessages(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_moremessages()), request)


@router.post("/api/morechildren")
async def POST_morechildren(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_morechildren()), request)


# -- Subreddit settings / stylesheet --
@router.post("/api/site_admin")
async def POST_site_admin(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_site_admin()), request)


@router.post("/api/subreddit_stylesheet")
async def POST_subreddit_stylesheet(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_subreddit_stylesheet()), request)


@router.post("/api/delete_sr_img")
async def POST_delete_sr_img(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_delete_sr_img()), request)


@router.post("/api/delete_sr_header")
async def POST_delete_sr_header(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_delete_sr_header()), request)


@router.post("/api/delete_sr_icon")
async def POST_delete_sr_icon(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_delete_sr_icon()), request)


@router.post("/api/delete_sr_banner")
async def POST_delete_sr_banner(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_delete_sr_banner()), request)


@router.get("/api/upload_sr_img")
async def GET_upload_sr_img(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().GET_upload_sr_img()), request)


@router.post("/api/upload_sr_img")
async def POST_upload_sr_img(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_upload_sr_img()), request)


@router.post("/api/set_sr_style_enabled")
async def POST_set_sr_style_enabled(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_set_sr_style_enabled()), request)


# -- Subreddit rules --
@router.post("/api/add_subreddit_rule")
async def POST_add_subreddit_rule(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_add_subreddit_rule()), request)


@router.post("/api/update_subreddit_rule")
async def POST_update_subreddit_rule(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_update_subreddit_rule()), request)


@router.post("/api/remove_subreddit_rule")
async def POST_remove_subreddit_rule(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_remove_subreddit_rule()), request)


# -- Flair --
@router.post("/api/flair")
async def POST_flair(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_flair()), request)


@router.post("/api/deleteflair")
async def POST_deleteflair(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_deleteflair()), request)


@router.post("/api/flaircsv")
async def POST_flaircsv(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_flaircsv()), request)


@router.post("/api/setflairenabled")
async def POST_setflairenabled(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_setflairenabled()), request)


@router.post("/api/flairconfig")
async def POST_flairconfig(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_flairconfig()), request)


@router.post("/api/flairtemplate")
async def POST_flairtemplate(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_flairtemplate()), request)


@router.post("/api/deleteflairtemplate")
async def POST_deleteflairtemplate(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_deleteflairtemplate()), request)


@router.post("/api/clearflairtemplates")
async def POST_clearflairtemplates(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_clearflairtemplates()), request)


@router.post("/api/flairselector")
async def POST_flairselector(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_flairselector()), request)


@router.post("/api/selectflair")
async def POST_selectflair(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_selectflair()), request)


# -- Gold / trophies / creddits --
@router.post("/api/claimgold")
async def POST_claimgold(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_claimgold()), request)


@router.post("/api/givetrophy")
async def POST_givetrophy(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_givetrophy()), request)


@router.post("/api/removetrophy")
async def POST_removetrophy(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_removetrophy()), request)


@router.post("/api/givecreddits")
async def POST_givecreddits(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_givecreddits()), request)


@router.post("/api/givegold")
async def POST_givegold(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_givegold()), request)


@router.post("/api/generate_payment_blob")
async def POST_generate_payment_blob(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_generate_payment_blob()), request)


@router.post("/api/modify_payment_blob")
async def POST_modify_payment_blob(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_modify_payment_blob()), request)


@router.post("/api/request_promo")
async def POST_request_promo(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_request_promo()), request)


# -- OAuth apps --
@router.post("/api/revokeapp")
async def POST_revokeapp(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_revokeapp()), request)


@router.post("/api/updateapp")
async def POST_updateapp(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_updateapp()), request)


@router.post("/api/adddeveloper")
async def POST_adddeveloper(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_adddeveloper()), request)


@router.post("/api/removedeveloper")
async def POST_removedeveloper(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_removedeveloper()), request)


@router.post("/api/deleteapp")
async def POST_deleteapp(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_deleteapp()), request)


@router.post("/api/setappicon")
async def POST_setappicon(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_setappicon()), request)


# -- Quarantine --
@router.post("/api/quarantine")
async def POST_quarantine(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_quarantine()), request)


@router.post("/api/quarantine_optout")
async def POST_quarantine_optout_api(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_quarantine_optout()), request)


@router.post("/api/quarantine_optin")
async def POST_quarantine_optin(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_quarantine_optin()), request)


# -- Miscellaneous --
@router.post("/api/expando")
async def POST_expando(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_expando()), request)


@router.post("/api/edit_error")
async def POST_edit_error(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_edit_error()), request)


@router.post("/api/editaward")
async def POST_editaward(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_editaward()), request)


@router.post("/api/search_reddit_names")
async def POST_search_reddit_names(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_search_reddit_names()), request)


@router.post("/api/disable_ui")
async def POST_disable_ui(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(await _call(ApiController().POST_disable_ui()), request)


@router.post("/api/set_nsfw_media_pref")
async def POST_set_nsfw_media_pref(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_set_nsfw_media_pref()), request)


@router.post("/api/set_left_bar_collapsed")
async def POST_set_left_bar_collapsed(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_set_left_bar_collapsed()), request)


@router.post("/api/server_seconds_visibility")
async def POST_server_seconds_visibility(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_server_seconds_visibility()), request)


@router.post("/api/add_admin_note")
async def POST_add_admin_note(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_add_admin_note()), request)


@router.post("/api/hide_locationbar")
async def POST_hide_locationbar(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_hide_locationbar()), request)


@router.post("/api/use_global_defaults")
async def POST_use_global_defaults(request: Request):
    from r2.controllers.api import ApiController
    return _to_response(
        await _call(ApiController().POST_use_global_defaults()), request)
