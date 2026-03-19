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

from hashlib import md5
import sys
import traceback

import sentry_sdk

from r2.lib.context import request
from r2.lib.context import c
from r2.lib.app_globals import g
from r2.lib.app_globals import Globals


def get_operational_exceptions():
    import _pylibmc
    import sqlalchemy.exc
    import r2.lib.lock
    import r2.lib.cache
    from r2.models.account import NotFound

    return (
        SystemExit,  # gunicorn is shutting us down
        _pylibmc.MemcachedError,
        NotFound,
        r2.lib.lock.TimeoutExpired,
        sqlalchemy.exc.OperationalError,
        sqlalchemy.exc.IntegrityError,
    )


# Keys / types to strip from stack frame locals before sending to Sentry.
_KEYS_TO_REMOVE = (
    "self",
    "__traceback_supplement__",
)
_CLASSES_TO_REMOVE = (Globals,)


def _sanitize_before_send(event, _hint):
    """Strip large/sensitive locals from stack frames before sending to Sentry."""

    def remove_keys(obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                if k in _KEYS_TO_REMOVE:
                    obj.pop(k)
                elif isinstance(obj[k], _CLASSES_TO_REMOVE):
                    obj.pop(k)
                elif isinstance(obj[k], str):
                    contains_forbidden = any(
                        cls.__name__ in obj[k] for cls in _CLASSES_TO_REMOVE
                    )
                    if contains_forbidden:
                        obj.pop(k)
                elif isinstance(obj[k], (list, dict)):
                    remove_keys(obj[k])
        elif isinstance(obj, list):
            for v in obj:
                if isinstance(v, (list, dict)):
                    remove_keys(v)

    for exc_val in event.get("exception", {}).get("values", []):
        for frame in exc_val.get("stacktrace", {}).get("frames", []):
            if "vars" in frame:
                remove_keys(frame["vars"])

    return event


class RavenErrorReporter:
    """Sentry error reporter (replaces EOL raven.Client)."""

    HEADER_WHITELIST = frozenset((
        "user-agent",
        "host",
        "accept",
        "accept-encoding",
        "accept-language",
        "referer",
    ))

    @classmethod
    def get_module_versions(cls):
        return {
            repo: commit_hash[:6]
            for repo, commit_hash in g.versions.items()
        }

    @classmethod
    def _get_release_hash(cls):
        release_str = '|'.join(
            f"{repo}:{commit_hash}"
            for repo, commit_hash in sorted(g.versions.items())
        )
        return md5(release_str.encode()).hexdigest()

    @classmethod
    def _init_sentry(cls):
        sentry_sdk.init(
            dsn=g.sentry_dsn,
            release=cls._get_release_hash(),
            environment=g.pool_name,
            before_send=_sanitize_before_send,
            # Don't auto-instrument — we manage capture explicitly.
            default_integrations=False,
        )

    @classmethod
    def capture_exception(cls, exc_info=None):
        if exc_info is None:
            # Capture as close to the exception site as possible when
            # possible; sys.exc_info() can give unexpected results.
            exc_info = sys.exc_info()

        if exc_info[0] is None:
            return

        if issubclass(exc_info[0], get_operational_exceptions()):
            return

        cls._init_sentry()

        with sentry_sdk.push_scope() as scope:
            if g.running_as_script:
                culprit = f'script: "{sys.argv[-1]}"'
                scope.set_tag("culprit", culprit)
            else:
                headers = {
                    k: v for k, v in request.headers.items()
                    if k.lower() in cls.HEADER_WHITELIST
                }
                scope.set_context("request", {
                    "url": request.path,
                    "method": request.method,
                    "query_string": request.query_string,
                    "data": request.body,
                    "headers": headers,
                })

                if "app" in request.GET:
                    scope.set_tag("app", request.GET["app"])

                scope.set_context("reddit", {
                    "language": c.lang,
                    "render_style": c.render_style,
                    "subreddit": c.site.name if c.site else None,
                })

                if c.user_is_loggedin:
                    scope.user = {"id": c.user._id}

                if c.oauth2_client:
                    scope.set_tag("oauth_client_id", c.oauth2_client._id)
                    scope.set_tag("oauth_client_name", c.oauth2_client.name)

                scope.set_context("modules", cls.get_module_versions())
                scope.set_tag("culprit", request.path)

            sentry_sdk.capture_exception(exc_info)

    def report(self, exc_data):
        self.capture_exception()


def write_error_summary(error):
    """Log a single-line summary of the error for easy log grepping."""
    fullpath = request.environ.get('FULLPATH', request.path)
    uid = c.user._id if c.user_is_loggedin else '-'
    g.log.error("E: %s U: %s FP: %s", error, uid, fullpath)


class LoggingErrorReporter:
    """Reporter that writes exceptions to g.log."""

    def report(self, exc_data):
        # exception_formatted is the output of traceback.format_exception_only
        exception = exc_data.exception_formatted[-1].strip()

        # First emit a single-line summary — great for grepping the log.
        write_error_summary(exception)

        # Then emit the full traceback line by line.
        for line in traceback.format_exc().splitlines():
            g.log.warning(line)
