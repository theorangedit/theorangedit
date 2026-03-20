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
OAuth2 frontend and access-token endpoints — Phase D-3 migration.

Migrated from:
  r2.controllers.oauth2.OAuth2FrontendController  → /api/v1/authorize
  r2.controllers.oauth2.OAuth2AccessController   → /api/v1/access_token
                                                   /api/v1/revoke_token
"""

from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse, Response

from r2.lib.context import request, response
from r2.lib.context import c
from r2.lib.app_globals import g
from r2.lib.i18n import _
from r2.config.extensions import set_extension
from r2.lib.base import abort
from r2.controllers.reddit_base import require_https, abort_with_error
from r2.lib.pages import RedditError
from r2.lib.strings import strings
from r2.models import Account, admintools, create_gift_gold, send_system_message
from r2.models.token import (
    OAuth2Client, OAuth2AuthorizationCode, OAuth2AccessToken,
    OAuth2RefreshToken, OAuth2Scope)
from r2.lib.errors import BadRequestError, ForbiddenError, errors
from r2.lib.pages import OAuth2AuthorizationPage
from r2.lib.require import RequirementException, require
from r2.lib.utils import constant_time_compare, parse_http_basic, UrlParser
from r2.lib.validator import (
    nop,
    validate,
    VRequired,
    VThrottledLogin,
    VOneOf,
    VUser,
    VModhash,
    VOAuth2ClientID,
    VOAuth2Scope,
    VOAuth2RefreshToken,
    VRatelimit,
    VLength,
)

router = APIRouter()

COMMON_REDDIT_HEADERS = ", ".join((
    "X-Ratelimit-Used",
    "X-Ratelimit-Remaining",
    "X-Ratelimit-Reset",
    "X-Moose",
))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _update_redirect_uri(base_redirect_uri, params, as_fragment=False):
    parsed = UrlParser(base_redirect_uri)
    if as_fragment:
        parsed.fragment = urlencode(params)
    else:
        parsed.update_query(**params)
    return parsed.unparse()


def _get_device_id(client):
    if client.is_first_party():
        return getattr(request.state, '_form_data', {}).get('device_id')


def _abort_oauth_error(error):
    g.stats.simple_event('oauth2.errors.%s' % error)
    abort(BadRequestError(error))


def _check_redirect_uri(client, redirect_uri):
    if (errors.OAUTH2_INVALID_CLIENT, 'client_id') in c.errors:
        _abort_oauth_error(errors.OAUTH2_INVALID_CLIENT)
    if not redirect_uri or redirect_uri != client.redirect_uri:
        _abort_oauth_error(errors.OAUTH2_INVALID_REDIRECT_URI)


def _check_response_type_and_scope(response_type, scope):
    if (errors.INVALID_OPTION, 'response_type') in c.errors:
        _abort_oauth_error(errors.OAUTH2_INVALID_RESPONSE_TYPE)
    if (errors.OAUTH2_INVALID_SCOPE, 'scope') in c.errors:
        _abort_oauth_error(errors.OAUTH2_INVALID_SCOPE)


def _check_client_type_and_duration(response_type, client, duration):
    if response_type == "token" and client.is_confidential():
        _abort_oauth_error(errors.OAUTH2_CONFIDENTIAL_TOKEN)
    if response_type == "token" and duration != "temporary":
        _abort_oauth_error(errors.OAUTH2_NO_REFRESH_TOKENS_ALLOWED)


def _check_employee_grants(client, scope):
    if not c.user.employee or not client or not scope:
        return
    if client._id in g.employee_approved_clients:
        return
    if client._id in g.mobile_auth_allowed_clients:
        return
    if scope.scopes == {"identity"}:
        return
    error_page = RedditError(
        title=_('this app has not been approved for use with employee accounts'),
        message="",
    )
    request.state.usable_error_content = error_page.render()
    abort(403)


def _error_response(state, redirect_uri, as_fragment=False):
    resp = {"state": state}
    if (errors.OAUTH2_ACCESS_DENIED, "authorize") in c.errors:
        resp["error"] = "access_denied"
    elif (errors.INVALID_MODHASH, None) in c.errors:
        resp["error"] = "access_denied"
    else:
        resp["error"] = "invalid_request"
    final_redirect = _update_redirect_uri(redirect_uri, resp, as_fragment)
    return RedirectResponse(url=final_redirect, status_code=302)


async def _get_client_auth():
    auth = request.headers.get("Authorization")
    try:
        client_id, client_secret = parse_http_basic(auth)
        require(client_id)
        try:
            client = await OAuth2Client._byID(client_id)
        except Exception:
            client = None
        require(client)
        if client.is_confidential():
            require(client_secret)
            require(constant_time_compare(client.secret, client_secret))
        return client
    except RequirementException:
        abort(401, headers=[("WWW-Authenticate", 'Basic realm="reddit"')])


def _check_for_errors():
    if (errors.INVALID_OPTION, "scope") in c.errors:
        return {"error": "invalid_scope"}
    return {"error": "invalid_request"}


def _make_new_token_response(access_token, refresh_token=None):
    if not access_token:
        return {"error": "invalid_grant"}
    expires_in = int(access_token._ttl) if access_token._ttl else None
    resp = {
        "access_token": access_token._id,
        "token_type": access_token.token_type,
        "expires_in": expires_in,
        "scope": access_token.scope,
    }
    if refresh_token:
        resp["refresh_token"] = refresh_token._id
    if access_token.device_id:
        resp['device_id'] = access_token.device_id
    return resp


def _cors_headers():
    """Build CORS response headers when an Origin header is present."""
    if "Origin" not in request.headers:
        return {}
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Headers": "Authorization, ",
        "Access-Control-Allow-Credentials": "false",
        "Access-Control-Expose-Headers": COMMON_REDDIT_HEADERS,
    }


# ---------------------------------------------------------------------------
# Access-token sub-handlers (called from POST_access_token)
#
# These are internal helpers, not route handlers.  Validators are applied via
# @validate with a no-op _on_error so that validation errors accumulate in
# c.errors without aborting; each function handles c.errors in its body.
# All params default to None so fn(**{}) is safe when kw is incomplete.
# ---------------------------------------------------------------------------

@validate(code=nop("code"),
          redirect_uri=VRequired("redirect_uri",
                                 errors.OAUTH2_INVALID_REDIRECT_URI),
          _on_error=lambda err: None)
def _access_token_code(code=None, redirect_uri=None):
    if not code:
        c.errors.add("NO_TEXT", field="code")
    if c.errors:
        return _check_for_errors(), 400

    access_token = None
    refresh_token = None
    client = c.oauth2_client
    auth_token = OAuth2AuthorizationCode.use_token(code, client._id, redirect_uri)

    if auth_token:
        if auth_token.refreshable:
            refresh_token = OAuth2RefreshToken._new(
                client_id=auth_token.client_id,
                user_id=auth_token.user_id,
                scope=auth_token.scope,
            )
            g.stats.simple_event('oauth2.access_token_code.refresh_token_create')
        device_id = _get_device_id(client)
        access_token = OAuth2AccessToken._new(
            client_id=auth_token.client_id,
            user_id=auth_token.user_id,
            scope=auth_token.scope,
            refresh_token=refresh_token._id if refresh_token else "",
            device_id=device_id,
        )
        g.stats.simple_event('oauth2.access_token_code.access_token_create')

    return _make_new_token_response(access_token, refresh_token), 200


@validate(refresh_token=VOAuth2RefreshToken("refresh_token"),
          _on_error=lambda err: None)
def _access_token_refresh(refresh_token=None):
    access_token = None
    if refresh_token:
        if refresh_token.client_id == c.oauth2_client._id:
            access_token = OAuth2AccessToken._new(
                refresh_token.client_id, refresh_token.user_id,
                refresh_token.scope,
                refresh_token=refresh_token._id)
            g.stats.simple_event('oauth2.access_token_refresh.access_token_create')
        else:
            g.stats.simple_event('oauth2.errors.OAUTH2_INVALID_REFRESH_TOKEN')
            c.errors.add(errors.OAUTH2_INVALID_REFRESH_TOKEN)
    else:
        g.stats.simple_event('oauth2.errors.NO_TEXT')
        c.errors.add("NO_TEXT", field="refresh_token")

    if c.errors:
        return _check_for_errors(), 400
    g.stats.simple_event('oauth2.access_token_refresh.success')
    return _make_new_token_response(access_token), 200


@validate(user=VThrottledLogin(["username", "password"]),
          scope=nop("scope"),
          _on_error=lambda err: None)
def _access_token_password(user=None, scope=None):
    client = c.oauth2_client
    if client.app_type != "script":
        g.stats.simple_event('oauth2.errors.PASSWORD_UNAUTHORIZED_CLIENT')
        return {"error": "unauthorized_client",
                "error_description": "Only script apps may use password auth"}, 400
    dev_ids = client._developer_ids
    if not user or user._id not in dev_ids:
        g.stats.simple_event('oauth2.errors.INVALID_GRANT')
        return {"error": "invalid_grant"}, 400
    if c.errors:
        return _check_for_errors(), 400
    if scope:
        scope = OAuth2Scope(scope)
        if not scope.is_valid():
            g.stats.simple_event('oauth2.errors.PASSWORD_INVALID_SCOPE')
            c.errors.add(errors.INVALID_OPTION, "scope")
            return {"error": "invalid_scope"}, 400
    else:
        scope = OAuth2Scope(OAuth2Scope.FULL_ACCESS)
    device_id = _get_device_id(client)
    access_token = OAuth2AccessToken._new(
        client_id=client._id,
        user_id=user._id36,
        scope=scope,
        device_id=device_id,
    )
    g.stats.simple_event('oauth2.access_token_password.access_token_create')
    return _make_new_token_response(access_token), 200


@validate(scope=nop("scope"), _on_error=lambda err: None)
def _access_token_client_credentials(scope=None):
    client = c.oauth2_client
    if not client.is_confidential():
        g.stats.simple_event('oauth2.errors.CLIENT_CREDENTIALS_UNAUTHORIZED_CLIENT')
        return {"error": "unauthorized_client",
                "error_description": "Only confidential clients may use client_credentials auth"}, 400
    if scope:
        scope = OAuth2Scope(scope)
        if not scope.is_valid():
            g.stats.simple_event('oauth2.errors.CLIENT_CREDENTIALS_INVALID_SCOPE')
            c.errors.add(errors.INVALID_OPTION, "scope")
            return {"error": "invalid_scope"}, 400
    else:
        scope = OAuth2Scope(OAuth2Scope.FULL_ACCESS)
    device_id = _get_device_id(client)
    access_token = OAuth2AccessToken._new(
        client_id=client._id,
        user_id="",
        scope=scope,
        device_id=device_id,
    )
    g.stats.simple_event('oauth2.access_token_client_credentials.access_token_create')
    return _make_new_token_response(access_token), 200


@validate(scope=nop("scope"),
          device_id=VLength("device_id", 50, min_length=20),
          _on_error=lambda err: None)
def _access_token_extension_client_credentials(scope=None, device_id=None):
    if ((errors.NO_TEXT, "device_id") in c.errors or
            (errors.TOO_SHORT, "device_id") in c.errors or
            (errors.TOO_LONG, "device_id") in c.errors):
        g.stats.simple_event('oauth2.errors.BAD_DEVICE_ID')
        return {"error": "invalid_request",
                "error_description": "bad device_id"}, 400
    client = c.oauth2_client
    if scope:
        scope = OAuth2Scope(scope)
        if not scope.is_valid():
            g.stats.simple_event(
                'oauth2.errors.EXTENSION_CLIENT_CREDENTIALS_INVALID_SCOPE')
            c.errors.add(errors.INVALID_OPTION, "scope")
            return {"error": "invalid_scope"}, 400
    else:
        scope = OAuth2Scope(OAuth2Scope.FULL_ACCESS)
    access_token = OAuth2AccessToken._new(
        client_id=client._id,
        user_id="",
        scope=scope,
        device_id=device_id,
    )
    g.stats.simple_event(
        'oauth2.access_token_extension_client_credentials.access_token_create')
    return _make_new_token_response(access_token), 200


# ---------------------------------------------------------------------------
# Frontend routes: GET/POST /api/v1/authorize
# ---------------------------------------------------------------------------

@router.get("/api/v1/authorize")
@validate(VUser(),
          response_type=VOneOf("response_type", ("code", "token")),
          client=VOAuth2ClientID(),
          redirect_uri=VRequired("redirect_uri", errors.OAUTH2_INVALID_REDIRECT_URI),
          scope=VOAuth2Scope(),
          state=VRequired("state", errors.NO_TEXT),
          duration=VOneOf("duration", ("temporary", "permanent"),
                          default="temporary"))
async def GET_authorize(response_type=None, client=None, redirect_uri=None,
                        scope=None, state=None, duration=None):
    """
    First step in OAuth 2.0 authentication.  Prompts the user for
    credentials and asks if they wish to authorize the application.
    """
    require_https()
    _check_employee_grants(client, scope)
    _check_redirect_uri(client, redirect_uri)
    _check_response_type_and_scope(response_type, scope)
    _check_client_type_and_duration(response_type, client, duration)
    if not c.errors:
        content = OAuth2AuthorizationPage(
            client, redirect_uri, scope, state, duration, response_type).render()
        return Response(content=content, media_type="text/html")
    _abort_oauth_error(errors.INVALID_OPTION)


@router.post("/api/v1/authorize")
@validate(VUser(),
          VModhash(fatal=False),
          client=VOAuth2ClientID(),
          redirect_uri=VRequired("redirect_uri", errors.OAUTH2_INVALID_REDIRECT_URI),
          scope=VOAuth2Scope(),
          state=VRequired("state", errors.NO_TEXT),
          duration=VOneOf("duration", ("temporary", "permanent"),
                          default="temporary"),
          authorize=VRequired("authorize", errors.OAUTH2_ACCESS_DENIED),
          response_type=VOneOf("response_type", ("code", "token"),
                               default="code"))
async def POST_authorize(authorize=None, client=None, redirect_uri=None,
                         scope=None, state=None, duration=None,
                         response_type=None):
    """Endpoint for OAuth2 authorization."""
    require_https()
    _check_employee_grants(client, scope)
    _check_redirect_uri(client, redirect_uri)
    _check_response_type_and_scope(response_type, scope)
    _check_client_type_and_duration(response_type, client, duration)

    if c.errors:
        return _error_response(state, redirect_uri,
                               as_fragment=(response_type == "token"))

    if response_type == "code":
        code = await OAuth2AuthorizationCode.create(
            account_id=c.user._id,
            data={'client_id': client._id, 'redirect_uri': redirect_uri,
                  'user_id': c.user._id36, 'scope': str(scope),
                  'permanent': duration == "permanent"},
        )
        resp = {"code": code._id, "state": state}
        final_redirect = _update_redirect_uri(redirect_uri, resp)
        g.stats.simple_event('oauth2.POST_authorize.authorization_code_create')
    elif response_type == "token":
        device_id = _get_device_id(client)
        token = await OAuth2AccessToken.create(
            account_id=c.user._id,
            data={'client_id': client._id, 'user_id': c.user._id36,
                  'scope': str(scope), 'device_id': device_id},
        )
        resp = _make_new_token_response(token)
        resp["state"] = state
        final_redirect = _update_redirect_uri(redirect_uri, resp, as_fragment=True)
        g.stats.simple_event('oauth2.POST_authorize.access_token_create')

    if (g.live_config.get('mobile_gild_first_login') and
            not c.user.has_used_mobile_app and
            client._id in g.mobile_auth_gild_clients):
        buyer = Account.system_user()
        admintools.adjust_gold_expiration(c.user, days=g.mobile_auth_gild_time)
        create_gift_gold(
            buyer._id, c.user._id, g.mobile_auth_gild_time,
            datetime.now(g.tz), signed=True, note='first_mobile_auth')
        subject = 'Let there be gold! Reddit just sent you Reddit gold!'
        message = (
            "Thank you for using the Reddit mobile app!  As a thank you "
            "for logging in during launch week, you've been gifted %s of "
            "Reddit Gold.\n\n"
            "Reddit Gold is Reddit's premium membership program, which "
            "grants you: \n"
            "An ads-free experience in Reddit's mobile apps, and\n"
            "Extra site features on desktop\n\n"
            "Discuss and get help on the features and perks at "
            "r/goldbenefits."
        ) % g.mobile_auth_gild_message
        message += '\n\n' + strings.gold_benefits_msg
        send_system_message(c.user, subject, message, add_to_sent=False)
        c.user.has_used_mobile_app = True
        await c.user._commit()

    return RedirectResponse(url=final_redirect, status_code=302)


# ---------------------------------------------------------------------------
# Access-token routes: /api/v1/access_token, /api/v1/revoke_token
# ---------------------------------------------------------------------------

@router.options("/api/v1/access_token")
async def OPTIONS_access_token():
    return Response(headers=_cors_headers())


@router.post("/api/v1/access_token")
@validate(grant_type=VOneOf("grant_type", (
    "authorization_code",
    "refresh_token",
    "password",
    "client_credentials",
    "https://oauth.reddit.com/grants/installed_client",
)), _on_error=lambda err: None)
async def POST_access_token(grant_type=None):
    """Exchange an OAuth2 authorization code or refresh token for an access token."""
    if g.disallow_db_writes:
        abort(403)
    set_extension("json")
    require_https()
    c.oauth2_client = await _get_client_auth()
    cors = _cors_headers()

    if grant_type == "authorization_code":
        data, status_code = await _access_token_code()
    elif grant_type == "refresh_token":
        data, status_code = await _access_token_refresh()
    elif grant_type == "password":
        data, status_code = await _access_token_password()
    elif grant_type == "client_credentials":
        data, status_code = await _access_token_client_credentials()
    elif grant_type == "https://oauth.reddit.com/grants/installed_client":
        data, status_code = await _access_token_extension_client_credentials()
    else:
        data, status_code = {"error": "unsupported_grant_type"}, 400

    return JSONResponse(data, status_code=status_code, headers=cors)


@router.options("/api/v1/revoke_token")
async def OPTIONS_revoke_token():
    return Response(headers=_cors_headers())


@router.post("/api/v1/revoke_token")
@validate(
    VRatelimit(rate_user=False, rate_ip=True, prefix="rate_revoke_token_"),
    token_id=nop("token"),
    token_hint=VOneOf("token_type_hint", ("access_token", "refresh_token")),
    _on_error=lambda err: None,
)
async def POST_revoke_token(token_id=None, token_hint=None):
    """Revoke an OAuth2 access or refresh token."""
    if g.disallow_db_writes:
        abort(403)
    set_extension("json")
    require_https()
    c.oauth2_client = await _get_client_auth()
    cors = _cors_headers()

    # Per RFC 7009: success if the token is no longer valid.
    if not token_id:
        return Response(status_code=204, headers=cors)

    from r2.models.token import NotFound as TokenNotFound
    types = (OAuth2AccessToken, OAuth2RefreshToken)
    if token_hint == "refresh_token":
        types = reversed(types)

    token = None
    for token_type in types:
        try:
            token = await token_type._byID(token_id)
            break
        except (TokenNotFound, Exception):
            g.stats.simple_event(
                'oauth2.POST_revoke_token.not_found.%s' % token_type.__name__)
            continue

    if token is None:
        return Response(status_code=204, headers=cors)

    if constant_time_compare(token.client_id, c.oauth2_client._id):
        await token._commit()
        return Response(status_code=204, headers=cors)
    else:
        g.stats.simple_event('oauth2.errors.REVOKE_TOKEN_UNAUTHORIZED_CLIENT')
        return JSONResponse({"error": "unauthorized_client"},
                            status_code=400, headers=cors)


# ---------------------------------------------------------------------------
# Helpers re-exported for use by other controllers that reference them
# ---------------------------------------------------------------------------

def require_oauth2_scope(*scopes):
    def oauth2_scope_wrap(fn):
        fn.oauth2_perms = {"required_scopes": scopes, "oauth2_allowed": True}
        return fn
    return oauth2_scope_wrap


def allow_oauth2_access(fn):
    fn.oauth2_perms = {"required_scopes": [], "oauth2_allowed": True}
    return fn
