"""
Per-request and application-level context objects.

All request-scoped objects are ContextVar proxies so they are safe for
async/threaded use.  Application globals (g) live in r2.lib.app_globals.

Usage::

    from r2.lib.context import c, request, response, session, config, url
    from r2.lib.app_globals import g
"""

from contextvars import ContextVar
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Per-request template context (c) — replaces pylons.tmpl_context
# ---------------------------------------------------------------------------

class _RequestContext:
    """
    Lenient namespace: reading an unset attribute returns '' (matching the
    old ``pylons.strict_tmpl_context = False`` behaviour).
    """
    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return ''


_tmpl_context_var: ContextVar[_RequestContext] = ContextVar(
    'r2.tmpl_context', default=None
)


class _ContextProxy:
    """
    Proxy that delegates to the ContextVar value so that::

        from r2.lib.context import c
        c.user = account

    works correctly in both sync and async contexts.
    """
    __slots__ = ()

    def _get(self):
        ctx = _tmpl_context_var.get()
        if ctx is None:
            ctx = _RequestContext()
            _tmpl_context_var.set(ctx)
        return ctx

    def __getattr__(self, name):
        return getattr(self._get(), name)

    def __setattr__(self, name, value):
        setattr(self._get(), name, value)

    def __delattr__(self, name):
        delattr(self._get(), name)

    def __contains__(self, name):
        return hasattr(self._get(), name)

    def __repr__(self):
        return repr(self._get())


c = _ContextProxy()


# ---------------------------------------------------------------------------
# Per-request HTTP objects — request, response
# ---------------------------------------------------------------------------

_request_var: ContextVar = ContextVar('r2.request', default=None)
_response_var: ContextVar = ContextVar('r2.response', default=None)


class _ObjectProxy:
    """Generic proxy to a ContextVar-backed object."""
    __slots__ = ('_var',)

    def __init__(self, var: ContextVar):
        object.__setattr__(self, '_var', var)

    def _get(self):
        return object.__getattribute__(self, '_var').get()

    def __getattr__(self, name):
        obj = self._get()
        if obj is None:
            raise RuntimeError(
                f"No active request — cannot access .{name} outside a "
                f"request context"
            )
        return getattr(obj, name)

    def __setattr__(self, name, value):
        if name == '_var':
            object.__setattr__(self, name, value)
            return
        obj = self._get()
        if obj is None:
            raise RuntimeError(
                f"No active request — cannot set .{name} outside a "
                f"request context"
            )
        setattr(obj, name, value)

    def __repr__(self):
        return repr(self._get())


request = _ObjectProxy(_request_var)
response = _ObjectProxy(_response_var)

# Session: thin namespace per request
_session_var: ContextVar = ContextVar('r2.session', default=None)
session = _ObjectProxy(_session_var)

# Config: set once at startup
config = SimpleNamespace()

# url helper: stub — populated at startup if needed
url = None


# ---------------------------------------------------------------------------
# Public helpers used by middleware to set up per-request context
# ---------------------------------------------------------------------------

def reset_request_context(starlette_request, starlette_response):
    """
    Called at the start of each request by RequestContextMiddleware.
    Binds Starlette request/response objects into ContextVars.
    """
    _request_var.set(starlette_request)
    _response_var.set(starlette_response)
    _tmpl_context_var.set(_RequestContext())
    _session_var.set(SimpleNamespace())
