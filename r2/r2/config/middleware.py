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
FastAPI / Starlette middleware stack.

Replaces the old Pylons + Paste middleware chain.  The public entry point is
``make_app(global_conf, **app_conf)`` which returns a fully configured
Starlette/FastAPI ASGI application.

Custom WSGI middleware from the old stack has been rewritten as Starlette
middleware where possible, or ported to request-lifecycle hooks.
"""

import importlib
import re
import tempfile
import urllib.parse
from threading import Lock

import simplejson

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from r2.config import hooks
from r2.config.environment import load_environment
from r2.config.extensions import extension_mapping, set_extension
from r2.lib.utils import is_subdomain, is_language_subdomain
from r2.lib import filters

from r2.lib.context import reset_request_context


# ---------------------------------------------------------------------------
# Request context middleware
# ---------------------------------------------------------------------------

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Binds per-request Starlette objects into ContextVar slots so that
    ``from r2.lib.context import request, response, c`` resolves correctly
    throughout the codebase.

    Also resets tmpl_context (c) to a fresh namespace on every request.
    """

    async def dispatch(self, request: Request, call_next):
        response = Response()
        reset_request_context(request, response)
        starlette_response = await call_next(request)
        return starlette_response


# ---------------------------------------------------------------------------
# Domain / subdomain middleware
# ---------------------------------------------------------------------------

class DomainMiddleware(BaseHTTPMiddleware):
    """
    Handles subdomain-to-subreddit redirection and domain prefix extraction.
    Mirrors the old WSGI DomainMiddleware logic.
    """

    async def dispatch(self, request: Request, call_next):
        from r2.lib.app_globals import g

        http_host = request.headers.get('host', 'localhost').lower()
        domain, _, port = http_host.partition(':')

        if port:
            try:
                request.state.request_port = int(port)
            except ValueError:
                pass

        is_media_only = (is_subdomain(domain, g.media_domain) and
                         g.domain != g.media_domain)
        if domain == "localhost" or is_media_only:
            return await call_next(request)

        if not is_subdomain(domain, g.domain):
            request.state.legacy_cname = domain
            return await call_next(request)

        ignored_suffix_len = len(g.domain)
        subdomains = domain[:-ignored_suffix_len - 1].split('.')

        sr_redirect = None
        prefix_parts = []
        for subdomain in subdomains[:]:
            extension = g.extension_subdomains.get(subdomain)
            if subdomain in g.reserved_subdomains:
                if subdomain not in g.ignored_subdomains:
                    prefix_parts.append(subdomain)
            elif extension:
                request.state.reddit_domain_extension = extension
            elif is_language_subdomain(subdomain):
                request.state.reddit_prefer_lang = subdomain
            else:
                sr_redirect = subdomain
                subdomains.remove(subdomain)

        if hasattr(request.state, 'reddit_prefer_lang'):
            prefix_parts.insert(0, request.state.reddit_prefer_lang)
        if prefix_parts:
            request.state.reddit_domain_prefix = '.'.join(prefix_parts)

        fullpath = request.url.path
        if request.url.query:
            fullpath += '?' + request.url.query

        if sr_redirect and fullpath:
            if not subdomains and g.domain_prefix:
                subdomains.append(g.domain_prefix)
            subdomains.append(g.domain)
            redir = "%s/r/%s/%s" % (
                '.'.join(subdomains), sr_redirect, fullpath)
            redir = g.default_scheme + "://" + redir.replace('//', '/')
            return RedirectResponse(url=redir, status_code=301)

        return await call_next(request)


# ---------------------------------------------------------------------------
# Subreddit path extraction middleware
# ---------------------------------------------------------------------------

class SubredditMiddleware(BaseHTTPMiddleware):
    sr_pattern = re.compile(r'^/r/([^/]{2,})(.*)')

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        m = self.sr_pattern.match(path)
        if m:
            request.state.subreddit = m.group(1)
            # Rewrite scope — Starlette Request path is immutable; store
            # the stripped path in state for the router to use.
            request.state.path_without_sr = m.group(2) or '/'
        return await call_next(request)


# ---------------------------------------------------------------------------
# Extension middleware
# ---------------------------------------------------------------------------

class ExtensionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        domain_ext = getattr(request.state, 'reddit_domain_extension', None)

        ext = None
        if '.' in path.split('/')[-1]:
            _, _, path_ext = path.rpartition('.')
            if path_ext in extension_mapping:
                ext = path_ext
                request.state.path_without_ext = path[:-(len(ext) + 1)]

        if ext is None and domain_ext in extension_mapping:
            ext = domain_ext

        if ext:
            request.state.extension = ext
            request.state.render_style, request.state.content_type = \
                extension_mapping[ext]
        else:
            request.state.render_style = 'html'
            request.state.content_type = 'text/html; charset=UTF-8'

        return await call_next(request)


# ---------------------------------------------------------------------------
# Upload size limiter
# ---------------------------------------------------------------------------

class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    MAX_SIZE = 1024 * 500  # 500 KiB

    async def dispatch(self, request: Request, call_next):
        if request.method == 'POST':
            cl = request.headers.get('content-length')
            if cl is None:
                return JSONResponse(
                    {"error": 411, "message": "Length Required"},
                    status_code=411,
                )
            try:
                cl_int = int(cl)
            except ValueError:
                return JSONResponse(
                    {"error": 400, "message": "Bad Request"},
                    status_code=400,
                )
            if cl_int > self.MAX_SIZE:
                msg = "too big. keep it under %d KiB" % (self.MAX_SIZE // 1024)
                return JSONResponse(
                    {"error": 413, "message": msg},
                    status_code=413,
                )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Response header safety (prevent response splitting)
# ---------------------------------------------------------------------------

class SafetyMiddleware(BaseHTTPMiddleware):
    _bad_chars = re.compile(r'[\r\n]')
    _sanitizer = re.compile(r'[\r\n]+[ \t]*')

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        sanitized_headers = {}
        for name, value in response.headers.items():
            if self._bad_chars.search(value):
                value = self._sanitizer.sub('', value)
            sanitized_headers[name] = value
        response.headers.update(sanitized_headers)
        return response


# ---------------------------------------------------------------------------
# Error document handler
# ---------------------------------------------------------------------------

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Converts Starlette HTTPExceptions to JSON or HTML error documents,
    mirroring the old error_mapper / ErrorDocuments behaviour.
    """
    code = exc.status_code
    detail = exc.detail or ""

    accept = request.headers.get('accept', '')
    render_style = getattr(request.state, 'render_style', 'html')
    is_api_request = render_style and render_style.startswith('api')

    if 'application/json' in accept or is_api_request:
        return JSONResponse(
            {"error": code, "message": detail or str(exc)},
            status_code=code,
        )

    # HTML error page — delegate to the /error/document/ endpoint
    params = {"code": code, "message": detail}
    ext = getattr(request.state, 'extension', None)
    if ext:
        error_url = '/error/document/.%s?%s' % (ext, urllib.parse.urlencode(params))
    else:
        error_url = '/error/document/?%s' % urllib.parse.urlencode(params)

    return RedirectResponse(url=error_url, status_code=302)


# ---------------------------------------------------------------------------
# Controller loader (equivalent to RedditApp.load_controllers)
# ---------------------------------------------------------------------------

_controllers_loaded = False
_hooks_registered = False
_loading_lock = Lock()


def _ensure_controllers_loaded(app_config):
    global _controllers_loaded, _hooks_registered

    if _controllers_loaded and _hooks_registered:
        return

    with _loading_lock:
        if not _controllers_loaded:
            controllers = importlib.import_module('r2.controllers')
            controllers.load_controllers()
            app_config['r2.plugins'].load_controllers()
            _controllers_loaded = True

        if not _hooks_registered:
            hooks.register_hooks()
            _hooks_registered = True


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def make_app(global_conf, full_stack=True, **app_conf):
    """
    Create and return the FastAPI/Starlette ASGI application.

    This replaces the old Pylons ``make_app`` / ``RedditApp`` factory.
    """
    config = load_environment(global_conf, app_conf)
    from r2.lib.app_globals import g

    # Deferred controller + hook loading
    _ensure_controllers_loaded(config)

    # Import the FastAPI app defined in r2.main (routers already registered)
    from r2.main import app

    # Register exception handlers
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # --- Middleware stack (outermost first) ---
    app.add_middleware(SafetyMiddleware)
    app.add_middleware(LimitUploadSizeMiddleware)
    app.add_middleware(ExtensionMiddleware)
    app.add_middleware(SubredditMiddleware)
    app.add_middleware(DomainMiddleware)
    app.add_middleware(RequestContextMiddleware)  # innermost — must run first

    # --- Static files ---
    static_path = config['r2.paths']['static_files']
    app.mount('/static', StaticFiles(directory=static_path), name='static')

    return app
