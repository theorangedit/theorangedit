"""
RedditRequestMiddleware — per-request lifecycle for the FastAPI stack.

Owns the DB session, auth, rate limits, subreddit setup, and response
finalization that previously lived in MinimalController.pre/post and
RedditController.pre/post (now deleted as of D-4).

This middleware is the sole owner of the request lifecycle.
"""

from __future__ import annotations

import collections
from datetime import datetime
from urllib.parse import quote, unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from r2.lib.context import c, reset_request_context


class RedditRequestMiddleware(BaseHTTPMiddleware):
    """
    Single Starlette middleware that owns the full per-request lifecycle:

      1. Opens an AsyncSession and stores it as c.db
      2. Calls _setup_request() — all of MinimalController.pre + RedditController.pre
      3. Calls call_next() to invoke the route handler
      4. Commits (or rolls back) the DB session
      5. Calls _finalize_response() — all of post() logic
      6. Returns the response

    This is the D-1 target.  During D-1 transition the legacy dispatcher
    still calls controller.pre/post; once D-3 is done those are no-ops.
    """

    async def dispatch(self, request: Request, call_next):
        from r2.lib.db.engine import AsyncSessionLocal
        from r2.lib.app_globals import g

        # Create a fresh per-request Response shell so that c.cookies and
        # response.headers writes during pre() have somewhere to land.
        shell_response = Response()
        reset_request_context(request, shell_response)

        # Cache form data synchronously for validators (which cannot await).
        # Must be done before _setup_request so validators in pre-handler
        # hooks (if any) also see the data.
        if request.method in ('POST', 'PUT', 'PATCH'):
            try:
                form_data = await request.form()
                request.state._form_data = dict(form_data)
            except Exception:
                request.state._form_data = {}
        else:
            request.state._form_data = {}

        async with AsyncSessionLocal() as db:
            c.db = db
            try:
                await _setup_request(request)
                starlette_response = await call_next(request)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        await _finalize_response(request, starlette_response)
        return starlette_response


# ---------------------------------------------------------------------------
# _setup_request — replaces MinimalController.pre + RedditController.pre
# ---------------------------------------------------------------------------

async def _setup_request(request: Request):
    """Run all per-request setup (auth, rate limits, subreddit context, etc.)."""
    from r2.lib.app_globals import g
    from r2.lib import baseplate_integration, hooks, ratelimit
    from r2.lib.base import abort
    from r2.lib.cookies import Cookies, Cookie, DELETE, delete_secure_session_cookie
    from r2.lib.errors import ErrorSet
    from r2.lib.loid import LoId
    from r2.lib.template_helpers import JSPreload
    from r2.lib.utils import SimpleSillyStub, extract_subdomain, is_subdomain
    from r2.config import feature
    from r2.config.extensions import is_api
    from r2.controllers.reddit_base import (
        UnloggedUser,
        delete_obsolete_cookies,
        enforce_https,
        generate_modhash,
        get_browser_langs,
        over18,
        ratelimit_agents,
        ratelimit_throttled,
        set_colors,
        set_content_type,
        set_iface_lang,
        set_multireddit,
        set_obey_over18,
        set_recent_clicks,
        set_subreddit,
    )
    from r2.models import (
        Account,
        FakeSubreddit,
        LabeledMulti,
        Random,
        RandomNSFW,
        RandomSubscription,
        Subreddit,
        valid_admin_cookie,
        valid_otp_cookie,
    )
    from r2.models.token import OAuth2AccessToken
    from r2.lib.require import RequirementException, require, require_split

    # ------------------------------------------------------------------ timer
    action = getattr(request.state, 'action_name', None)
    if action:
        controller = getattr(request.state, 'controller_name', 'unknown')
        key = "{}.{}".format(controller, action)
        c.request_timer = g.stats.get_timer("service_time.web." + key)
    else:
        key = request.method + " " + request.url.path
        c.request_timer = SimpleSillyStub()

    baseplate_integration.make_server_span(span_name=key).start()

    c.js_preload = JSPreload()
    c.response_wrapper = None
    c.start_time = datetime.now(g.tz)
    c.request_timer.start()
    g.reset_caches()

    # --------------------------------------------------------- basic context
    c.domain_prefix = getattr(request.state, 'reddit_domain_prefix', g.domain_prefix)
    c.secure = request.url.scheme == "https"
    c.request_origin = str(request.base_url)
    c.allow_framing = False
    c.referrer_policy = "origin"
    c.cdn_cacheable = (getattr(request.state, 'via_cdn', False) and
                       g.login_cookie not in request.cookies)

    # ----------------------------------------------------------- rate limits
    if not c.error_page:
        ratelimit_throttled()
        ratelimit_agents()

    # ---------------------------------------------------- raw_json opt-out
    if not hasattr(request.state, 'want_raw_json'):
        request.state.want_raw_json = (
            request.query_params.get("raw_json", "") == "1"
        )

    # ---------------------------------------------------- subreddit + content
    c.extension = getattr(request.state, 'extension', None)
    await set_subreddit()
    c.subdomain = extract_subdomain()
    c.errors = ErrorSet()
    c.cookies = Cookies()
    set_content_type()

    c.request_timer.intermediate("minimal-pre")
    c.update_last_visit = None

    # ----------------------------------------------------------- CORS check
    if is_subdomain(request.headers.get('host', ''), g.oauth_domain):
        _check_cors(request)

    # -------------------------------------------------- sitewide rate limits
    _run_sitewide_ratelimits()
    c.request_timer.intermediate("minimal-ratelimits")

    hooks.get_hook("reddit.request.minimal_begin").call()

    # ================================================================
    # RedditController.pre() logic from here on
    # ================================================================

    record_timings = g.admin_cookie in request.cookies or g.debug
    admin_bar_eligible = getattr(request.state, 'render_style', 'html') == 'html'
    if admin_bar_eligible and record_timings:
        g.stats.start_logging_timings()

    response.headers["X-UA-Compatible"] = "IE=edge"  # noqa: F821 (response proxy)

    # -------------------------------------------------- populate c.cookies
    if request.headers.get('host', '') != g.media_domain or g.media_domain == g.domain:
        cookie_counts = collections.Counter()
        for k, v in request.cookies.items():
            if k not in c.cookies:
                c.cookies[k] = Cookie(value=unquote(v), dirty=False)
                cookie_counts[Cookie.classify(k)] += 1
        for cookietype, count in cookie_counts.items():
            g.stats.simple_event("cookie.%s" % cookietype, count)

    delete_obsolete_cookies()

    # ---------------------------------------------------------- bearer token
    maybe_admin = False
    is_otpcookie_valid = False
    await _check_for_bearer_token()

    # ---------------------------------------------------------- cookie auth
    if not c.user:
        if c.extension != "rss":
            if not g.read_only_mode:
                c.user = await g.auth_provider.get_authenticated_account()
                if c.user and getattr(c.user, 'is_deleted', False):
                    c.user = None
            else:
                c.user = None
            c.user_is_loggedin = bool(c.user)

            admin_cookie = c.cookies.get(g.admin_cookie)
            if c.user_is_loggedin and admin_cookie:
                maybe_admin, first_login = valid_admin_cookie(admin_cookie.value)
                if maybe_admin:
                    _enable_admin_mode(c.user, first_login=first_login)
                else:
                    _disable_admin_mode(c.user)

            from r2.controllers.reddit_base import read_user_cookie
            otp_cookie = read_user_cookie(g.otp_cookie)
            if c.user_is_loggedin and otp_cookie:
                is_otpcookie_valid = valid_otp_cookie(otp_cookie)

        if not c.user:
            c.user = UnloggedUser(get_browser_langs())
            if not isinstance(c.user.pref_lang, str):
                c.user.pref_lang = g.lang
                await c.user._commit()

    # --------------------------------------------------------- user context
    if c.user_is_loggedin:
        _set_up_user_context()
        c.modhash = generate_modhash()
        c.user_is_admin = maybe_admin and c.user.name in g.admins
        c.user_is_sponsor = c.user_is_admin or c.user.name in g.sponsors
        c.otp_cached = is_otpcookie_valid
        from r2.models.subreddit import LabeledMulti as _LabeledMulti
        c.user_multis = await _LabeledMulti.by_owner(c.user, load_subreddits=False)
    else:
        c.user_multis = []

    enforce_https()
    c.request_timer.intermediate("base-auth")

    _run_sitewide_ratelimits()
    c.request_timer.intermediate("base-ratelimits")

    c.over18 = over18()
    set_obey_over18()
    await set_multireddit()
    set_iface_lang()
    await set_recent_clicks()
    set_colors()

    # -------------------------------------------------- store reddit_name
    if not isinstance(c.site, FakeSubreddit):
        request.state.reddit_name = c.site.name

    # ----------------------------------------------- random subreddit redirect
    _qs = request.url.query
    _path_qs = request.url.path + ("?" + _qs if _qs else "")

    if c.site == Random:
        c.site = Subreddit.random_reddit(user=c.user)
        site_path = c.site.path.strip('/')
        abort(302, location=_format_url("/" + site_path + _path_qs))
    elif c.site == RandomSubscription:
        if not c.user.gold:
            abort(302, location=_format_url('/gold/about'))
        c.site = Subreddit.random_subscription(c.user)
        site_path = c.site.path.strip('/')
        abort(302, location=_format_url('/' + site_path + _path_qs))
    elif c.site == RandomNSFW:
        c.site = Subreddit.random_reddit(over18=True, user=c.user)
        site_path = c.site.path.strip('/')
        abort(302, location=_format_url('/' + site_path + _path_qs))

    # ------------------------------------------- subreddit access checks
    if not request.url.path.startswith("/api/login/"):
        from r2.lib import pages
        from r2.lib.i18n import _

        if c.site.spammy() and not c.user_is_admin and not c.error_page:
            ban_info = getattr(c.site, "ban_info", {})
            message = ban_info.get('message') if "message" in ban_info else None
            errpage = pages.InterstitialPage(
                _("banned"),
                content=pages.BannedInterstitial(
                    message=message,
                    ban_time=ban_info.get("banned_at"),
                ),
            )
            request.state.usable_error_content = errpage.render()
            abort(404)

        if (not c.site.can_view(c.user) and not c.error_page and
                request.method != "OPTIONS"):
            allowed_to_view = c.site.is_allowed_to_view(c.user)

            if isinstance(c.site, LabeledMulti):
                abort(404)
            elif not allowed_to_view and c.site.type == 'gold_only':
                errpage = pages.InterstitialPage(
                    _("gold members only"),
                    content=pages.GoldOnlyInterstitial(
                        sr_name=c.site.name,
                        sr_description=c.site.public_description,
                    ),
                )
                request.state.usable_error_content = errpage.render()
                abort(403)
            elif not allowed_to_view:
                errpage = pages.InterstitialPage(
                    _("private"),
                    content=pages.PrivateInterstitial(
                        sr_name=c.site.name,
                        sr_description=c.site.public_description,
                    ),
                )
                request.state.usable_error_content = errpage.render()
                abort(403)
            else:
                if c.render_style != 'html':
                    abort(403)
                g.events.quarantine_event(
                    'quarantine_interstitial_view', c.site,
                    request=request, context=c)
                abort(302, location=_format_url("/quarantine"))

        # check over 18
        import re as _re
        _ua = request.headers.get('user-agent', '')
        _is_bot = bool(_re.search(r'(?:bot|crawler|spider|scraper)', _ua, _re.I))
        if (c.site.over_18 and not c.over18 and
                request.url.path != "/over18" and
                c.render_style == 'html' and
                not _is_bot):
            abort(302, location=_format_url("/over18"))

    # -------------------------------------------- stylesheet flags
    c.allow_styles = True
    c.can_apply_styles = False  # overridden by controllers that allow_stylesheets

    _theme_sr = None
    if c.user.pref_default_theme_sr and feature.is_enabled('stylesheets_everywhere'):
        try:
            from r2.models import NotFound
            _theme_sr = await Subreddit._by_name(c.user.pref_default_theme_sr)
        except Exception:
            pass
    has_style_override = bool(_theme_sr and _theme_sr.can_view(c.user))
    sr_stylesheet_enabled = c.user.use_subreddit_style(c.site)

    if not sr_stylesheet_enabled and not has_style_override:
        c.can_apply_styles = False

    c.bare_content = request.query_params.get('bare', False)
    c.show_admin_bar = admin_bar_eligible and (c.user_is_admin or g.debug)
    if not c.show_admin_bar:
        g.stats.end_logging_timings()

    hooks.get_hook("reddit.request.begin").call()
    c.request_timer.intermediate("base-pre")


# ---------------------------------------------------------------------------
# _finalize_response — replaces MinimalController.post + RedditController.post
# ---------------------------------------------------------------------------

async def _finalize_response(request: Request, starlette_response: Response):
    """Apply security headers, cookies, cache-control, and timing data."""
    from r2.lib.app_globals import g
    from r2.lib import hooks
    from r2.config import feature
    from r2.config.extensions import is_api
    from r2.controllers.reddit_base import flatten_response
    from r2.lib.cookies import CACHEABLE_COOKIES, upgrade_cookie_security
    import simplejson

    c.request_timer.intermediate("action")

    # ----------------------------------------------- response wrapper (JSONP)
    if c.response_wrapper and not getattr(c, 'is_exception_response', False):
        # For legacy controllers the body is in the ContextVar response; for
        # native routers it's in starlette_response.body.
        body = b''
        if hasattr(starlette_response, 'body'):
            try:
                body = starlette_response.body
            except Exception:
                pass
        if body:
            wrapped = c.response_wrapper(body.decode('utf-8', errors='replace'))
            starlette_response = Response(
                content=wrapped,
                media_type='application/javascript',
                headers=dict(starlette_response.headers),
            )

    # ----------------------------------------------- security headers
    if not c.allow_framing:
        starlette_response.headers["X-Frame-Options"] = "SAMEORIGIN"
    starlette_response.headers['X-Content-Type-Options'] = 'nosniff'
    starlette_response.headers['X-XSS-Protection'] = '1; mode=block'
    starlette_response.headers["X-UA-Compatible"] = "IE=edge"

    # ----------------------------------------------- HTTPS cookie upgrade
    if feature.is_enabled("force_https") and feature.is_enabled("upgrade_cookies"):
        upgrade_cookie_security()

    # ----------------------------------------------- cache-control
    dirty_cookies = (k for k, v in c.cookies.items() if v.dirty)
    would_poison = any((k not in CACHEABLE_COOKIES) for k in dirty_cookies)

    if c.user_is_loggedin or would_poison:
        starlette_response.headers['Expires'] = '-1'
        starlette_response.headers['Cache-Control'] = (
            'private, s-maxage=0, max-age=0, must-revalidate'
        )

    # ----------------------------------------------- rate limit headers
    if c.ratelimit_headers:
        starlette_response.headers.update(c.ratelimit_headers)

    # ----------------------------------------------- loid cookie
    if c.loid:
        c.loid.save(domain=g.domain)

    # ----------------------------------------------- write dirty cookies
    secure_cookies = feature.is_enabled("force_https")
    for k, v in c.cookies.items():
        if v.dirty:
            v_secure = v.secure if v.secure is not None else secure_cookies
            starlette_response.set_cookie(
                key=k,
                value=quote(v.value),
                domain=v.domain,
                expires=v.expires,
                secure=v_secure,
                httponly=getattr(v, 'httponly', False),
            )

    # ----------------------------------------------- visitor activity
    from r2.models import FakeSubreddit
    if not isinstance(c.site, FakeSubreddit) and not g.disallow_db_writes:
        if c.user_is_loggedin:
            c.site.record_visitor_activity("logged_in", c.user._fullname)

    if _should_update_last_visit():
        c.user.update_last_visit(c.start_time)

    hooks.get_hook("reddit.request.end").call()
    g.reset_caches()
    c.request_timer.intermediate("post")

    # ----------------------------------------------- tracing / stats
    c.trace.set_tag("user", c.user._fullname if c.user_is_loggedin else None)
    c.trace.set_tag("render_style", c.render_style)
    from r2.lib import baseplate_integration
    baseplate_integration.finish_server_span()
    c.request_timer.stop()
    g.stats.flush()

    # ----------------------------------------------- admin bar timing
    if c.render_style == 'html':
        _embed_html_timing_data(starlette_response)

    # ----------------------------------------------- CORS for logged-out API
    if (not c.cors_checked and request.method.upper() == "GET" and
            not c.user_is_loggedin and c.render_style == "api"):
        starlette_response.headers["Access-Control-Allow-Origin"] = "*"
        request_origin = request.headers.get('Origin')
        if request_origin and request_origin != g.origin:
            g.stats.simple_event('cors.api_request')
            g.stats.count_string('origins', request_origin)

    # ----------------------------------------------- tracking pixel
    from r2.lib.tracking import get_pageview_pixel_url
    from r2.controllers.reddit_base import make_url_https
    if g.tracker_url and request.method.upper() == "GET" and is_api():
        tracking_url = make_url_https(get_pageview_pixel_url())
        starlette_response.headers["X-Reddit-Tracking"] = tracking_url


# ---------------------------------------------------------------------------
# Private helpers extracted from controller class methods
# ---------------------------------------------------------------------------

def _run_sitewide_ratelimits():
    """Module-level equivalent of MinimalController.run_sitewide_ratelimits."""
    from r2.lib.app_globals import g
    from r2.lib import ratelimit
    from r2.lib.base import abort
    from r2.config.extensions import is_api
    from r2.lib.context import request

    if c.error_page:
        return

    if c.oauth_user and g.RL_OAUTH_SITEWIDE_ENABLED:
        type_ = "oauth"
        period = g.RL_OAUTH_RESET_SECONDS
        max_reqs = c.oauth2_client._max_reqs
        client_id = c.oauth2_access_token.client_id.encode("ascii")
        key = 'siterl-oauth-' + c.user._id36 + ":" + client_id
    elif c.cdn_cacheable:
        type_ = "cdn"
    elif not is_api():
        type_ = "web"
    elif g.RL_SITEWIDE_ENABLED:
        type_ = "api"
        max_reqs = g.RL_MAX_REQS
        period = g.RL_RESET_SECONDS
        key = 'siterl-api-' + (request.client.host if request.client else '')
    else:
        type_ = "none"

    g.stats.event_count("ratelimit.type", type_, sample_rate=0.01)
    if type_ in ("cdn", "web", "none"):
        return

    time_slice = ratelimit.get_timeslice(period)
    try:
        recent_reqs = ratelimit.record_usage(key, time_slice)
    except ratelimit.RatelimitError as e:
        g.log.info("ratelimit error: %s", e)
        return

    reqs_remaining = max(0, max_reqs - recent_reqs)
    c.ratelimit_headers = {
        "X-Ratelimit-Used": str(recent_reqs),
        "X-Ratelimit-Reset": str(time_slice.remaining),
        "X-Ratelimit-Remaining": str(reqs_remaining),
    }

    event_type = None
    if reqs_remaining <= 0:
        event_type = "hyperbolic" if recent_reqs > (2 * max_reqs) else "over"
        if g.ENFORCE_RATELIMIT:
            request.state.retry_after = time_slice.remaining
            abort(429)
    elif reqs_remaining < (0.1 * max_reqs):
        event_type = "close"

    if event_type is not None:
        g.stats.event_count("ratelimit.exceeded", event_type)
        if type_ == "oauth":
            g.stats.count_string("oauth.{}".format(event_type), client_id)


async def _check_for_bearer_token():
    """Module-level equivalent of OAuth2ResourceController.check_for_bearer_token."""
    from r2.lib.context import request
    auth = request.headers.get("Authorization")
    if not auth:
        return
    try:
        from r2.lib.require import require, require_split, RequirementException
        auth_scheme, bearer_token = require_split(auth, 2)
        require(auth_scheme.lower() == "bearer")
    except Exception:
        return
    await _authenticate_with_token(bearer_token)


async def _authenticate_with_token(bearer_token: str):
    """Module-level equivalent of OAuth2ResourceController.authenticate_with_token."""
    from r2.lib.app_globals import g
    from r2.lib.base import abort
    from r2.lib.require import RequirementException, require
    from r2.lib.context import request
    from r2.config.extensions import set_extension
    from r2.controllers.reddit_base import (
        UnloggedUser, get_browser_langs, require_https, require_domain,
        set_content_type,
    )
    from r2.models import Account
    from r2.models.token import OAuth2AccessToken, OAuth2Client, OAuth2Scope

    set_extension("json")
    set_content_type()
    require_https()
    require_domain(g.oauth_domain)

    try:
        access_token = await OAuth2AccessToken._byID(bearer_token)
        require(access_token)
        require(access_token.check_valid())
        c.oauth2_access_token = access_token
        if access_token.user_id:
            account = await Account._byID36(access_token.user_id, data=True)
            require(account)
            require(not account._deleted)
            c.user = c.oauth_user = account
            c.user_is_loggedin = True
        else:
            c.user = UnloggedUser(get_browser_langs())
            c.user_is_loggedin = False
        c.oauth2_client = await OAuth2Client._byID(access_token.client_id)
    except RequirementException:
        abort(401, headers=[
            ("WWW-Authenticate", 'Bearer realm="reddit", error="invalid_token"')
        ])


def _set_up_user_context():
    """Module-level equivalent of OAuth2ResourceController.set_up_user_context."""
    if c.user.inbox_count > 0:
        c.have_messages = True
    c.have_mod_messages = bool(c.user.modmsgtime)
    c.user_special_distinguish = c.user.special_distinguish()


def _enable_admin_mode(user, first_login=None):
    """Module-level equivalent of RedditController.enable_admin_mode."""
    from r2.lib.app_globals import g
    from r2.lib.cookies import Cookie
    from r2.config import feature
    admin_cookie = user.make_admin_cookie(first_login=first_login)
    c.cookies[g.admin_cookie] = Cookie(
        value=admin_cookie,
        httponly=True,
        secure=feature.is_enabled("force_https"),
    )


def _disable_admin_mode(user):
    """Module-level equivalent of RedditController.disable_admin_mode."""
    from r2.lib.app_globals import g
    from r2.lib.cookies import Cookie, DELETE
    c.cookies[g.admin_cookie] = Cookie(value='', expires=DELETE)


def _should_update_last_visit() -> bool:
    from r2.lib.app_globals import g
    from r2.lib.context import request
    if g.disallow_db_writes:
        return False
    if not c.user_is_loggedin:
        return False
    if c.update_last_visit is not None:
        return c.update_last_visit
    return request.method.upper() != "POST"


def _check_cors(request: Request):
    """Minimal CORS check for OAuth domain requests (from MinimalController)."""
    from r2.lib.app_globals import g
    from r2.lib.context import response
    from r2.controllers.reddit_base import MinimalController

    origin = request.headers.get("Origin")
    if c.cors_checked or not origin:
        return

    from r2.lib.utils import is_subdomain
    via_oauth = is_subdomain(request.headers.get('host', ''), g.oauth_domain)
    if via_oauth:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE"
        )
        response.headers["Access-Control-Allow-Headers"] = "Authorization, "
        response.headers["Access-Control-Allow-Credentials"] = "false"
        response.headers['Access-Control-Expose-Headers'] = (
            MinimalController.COMMON_REDDIT_HEADERS
        )
    c.cors_checked = True


def _embed_html_timing_data(starlette_response: Response):
    """Inject admin bar timing script into HTML response body."""
    import simplejson
    timings = None
    try:
        from r2.lib.app_globals import g
        timings = g.stats.end_logging_timings()
    except Exception:
        pass

    if not timings or not c.show_admin_bar or getattr(c, 'is_exception_response', False):
        return

    timings_data = [{
        "key": t.key,
        "start": round(t.start, 4),
        "end": round(t.end, 4),
    } for t in timings]

    try:
        body = starlette_response.body.decode('utf-8', errors='replace')
        body_parts = list(body.rpartition("</body>"))
        if body_parts[1]:
            script = (
                '<script type="text/javascript">'
                'window.r = window.r || {};'
                'r.timings = %s'
                '</script>'
            ) % simplejson.dumps(timings_data)
            body_parts.insert(1, script)
            new_body = "".join(body_parts).encode('utf-8')
            starlette_response._body = new_body
    except Exception:
        pass


def _format_url(path: str) -> str:
    """Equivalent of BaseController.format_output_url for module-level use."""
    from r2.lib.base import BaseController
    return BaseController.format_output_url(path)
