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

import re
import hashlib
import sys
from http.cookies import CookieError
from urllib.parse import quote
import urllib.request as urllib2

from r2.lib.context import request, session, config, response
from r2.lib.context import c
from r2.lib.app_globals import g
from r2.lib.i18n import N_, _, ungettext, get_lang
from starlette.exceptions import HTTPException


class WSGIController:
    """Minimal async-capable controller base replacing Pylons WSGIController."""

    async def pre(self):
        """Called before the action handler. Override in subclasses."""
        pass

    async def post(self):
        """Called after the action handler. Override in subclasses."""
        pass

    def on_validation_error(self, error):
        from r2.lib.errors import RedditError
        if isinstance(error, RedditError):
            abort(error.code or 400, error.message)
        else:
            abort(400, str(error))

from r2.lib.filters import spaceCompress, _force_unicode
from r2.lib.template_helpers import get_domain
from r2.lib.utils import Agent, UrlParser, query_string
from r2.lib.utils._utils import string2js, read_http_date

import logging
logging.getLogger('scgi-wsgi').setLevel(logging.CRITICAL)


def is_local_address(ip):
    return ip.startswith('10.') or ip == "127.0.0.1"


def abort(code_or_exception=None, detail="", headers=None, comment=None,
          **kwargs):
    """Raise an HTTPException and save it in request state for use by error pages."""
    if isinstance(code_or_exception, HTTPException):
        exc = code_or_exception
    else:
        status_code = (
            code_or_exception
            if isinstance(code_or_exception, int)
            else int(code_or_exception)
        )
        exc = HTTPException(status_code=status_code, detail=detail,
                            headers=headers)
    try:
        req = request._get()
        if req is not None:
            req.state.controller_exception = exc
    except Exception:
        pass
    raise exc


class BaseController(WSGIController):
    def pre(self): pass
    def post(self): pass

    def fix_cookie_header(self):
        """Detect and drop busted Cookie headers."""
        try:
            request.cookies
        except (CookieError, KeyError):
            cookie_val = request.headers.get('cookie', '')
            # Starlette request is immutable; log and continue
            g.log.warning("Bad cookie header received: %r" % cookie_val)
            if g.stats:
                g.stats.simple_event("cookie.bad_cookie_header")

    def _get_action_handler(self, name=None, method=None):
        name = name or getattr(request.state, 'action_name', None)
        method = method or request.method
        action = method + "_" + name if name else method
        return getattr(self, action, None)

    @classmethod
    def format_output_url(cls, url, **kw):
        preserve_extension = kw.pop("preserve_extension", True)
        u = UrlParser(url)

        if u.is_reddit_url():
            if 'port' not in kw:
                kw['port'] = getattr(request, 'port', None)
            if preserve_extension and c.extension:
                u.set_extension(c.extension)

        rv = _force_unicode(u.unparse()).encode('utf8')
        if b"\n" in rv or b"\r" in rv:
            abort(400)
        return rv

    @classmethod
    def intermediate_redirect(cls, form_path, sr_path=True, fullpath=None):
        from r2.lib.template_helpers import add_sr
        params = dict(dest=cls.format_output_url(
            fullpath or request.fullurl if hasattr(request, 'fullurl')
            else str(request.url)
        ))
        if c.extension == "widget" and request.query_params.get("callback"):
            params['callback'] = request.query_params.get("callback")

        path = add_sr(cls.format_output_url(form_path) +
                      query_string(params), sr_path=sr_path)
        abort(302, headers={"location": path})

    @classmethod
    def redirect(cls, dest, code=302, preserve_extension=True):
        dest = cls.format_output_url(dest or "/",
                                     preserve_extension=preserve_extension)
        abort(code, headers={"location": dest.decode('utf-8')
                              if isinstance(dest, bytes) else dest})


class EmbedHandler(urllib2.BaseHandler, urllib2.HTTPHandler,
                   urllib2.HTTPErrorProcessor, urllib2.HTTPDefaultErrorHandler):

    def http_redirect(self, req, fp, code, msg, hdrs):
        to = hdrs['Location']
        h = urllib2.HTTPRedirectHandler()
        r = h.redirect_request(req, fp, code, msg, hdrs, to)
        return embedopen.open(r)

    http_error_301 = http_redirect
    http_error_302 = http_redirect
    http_error_303 = http_redirect
    http_error_307 = http_redirect


embedopen = urllib2.OpenerDirector()
embedopen.add_handler(EmbedHandler())


def proxyurl(url):
    r = urllib2.Request(url, None, {})
    content = embedopen.open(r).read()
    return content
