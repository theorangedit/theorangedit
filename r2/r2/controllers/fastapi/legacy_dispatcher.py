"""
Legacy controller dispatcher.

During the incremental migration, most controllers are still written in
Pylons style (class with GET_foo / POST_foo methods).  This router acts as a
catch-all that dispatches requests to the appropriate legacy controller method
using the Routes map defined in r2.config.routing.

As controllers are ported to native FastAPI routers (in this package) they
are removed from the Routes map and this dispatcher stops seeing them.
"""

import inspect

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.exceptions import HTTPException

router = APIRouter()


async def _dispatch(request: Request, path: str):
    """
    Look up the controller + action for ``path`` in the Routes map and call
    the appropriate method.

    Opens an AsyncSession, stores it as c.db, runs pre() / handler / post(),
    and commits (or rolls back) the session before returning.

    Returns a Starlette Response or raises HTTPException.
    """
    from r2.lib.app_globals import g
    from r2.lib.context import c
    from r2.lib.db.engine import AsyncSessionLocal
    from r2 import controllers as ctrl_module

    routes_map = getattr(g, '_routes_map', None)
    if routes_map is None:
        raise HTTPException(status_code=404)

    environ = {
        'REQUEST_METHOD': request.method,
        'PATH_INFO': path,
        'SERVER_NAME': request.url.hostname,
        'SERVER_PORT': str(request.url.port or 80),
        'wsgi.url_scheme': request.url.scheme,
        'QUERY_STRING': request.url.query or '',
        'HTTP_HOST': request.headers.get('host', ''),
    }

    match = routes_map.match(environ=environ)
    if not match:
        raise HTTPException(status_code=404)

    controller_name = match.get('controller')
    action_name = match.get('action')

    if not controller_name or not action_name:
        raise HTTPException(status_code=404)

    controller_cls = ctrl_module.get_controller(controller_name)
    if controller_cls is None:
        raise HTTPException(status_code=404)

    meth = request.method.upper()
    if meth == 'HEAD':
        meth = 'GET'

    handler_name = meth + '_' + action_name
    controller = controller_cls()

    async with AsyncSessionLocal() as db:
        # Attach the DB session to the request context so validators and
        # service functions can access it via c.db without extra arguments.
        c.db = db

        try:
            # Run pre() hook (sets up c.user, c.site, etc.)
            if hasattr(controller, 'pre'):
                pre = controller.pre()
                if inspect.isawaitable(pre):
                    await pre

            handler = getattr(controller, handler_name, None)
            if handler is None:
                raise HTTPException(status_code=404)

            action_kwargs = {k: v for k, v in match.items()
                             if k not in ('controller', 'action')}
            result = handler(**action_kwargs)
            if inspect.isawaitable(result):
                result = await result

            if hasattr(controller, 'post'):
                post = controller.post()
                if inspect.isawaitable(post):
                    await post

            await db.commit()
        except HTTPException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

    if result is None:
        return Response(status_code=200)
    if isinstance(result, str):
        content_type = getattr(request.state, 'content_type',
                               'text/html; charset=UTF-8')
        return Response(content=result, media_type=content_type)
    if isinstance(result, bytes):
        content_type = getattr(request.state, 'content_type',
                               'text/html; charset=UTF-8')
        return Response(content=result, media_type=content_type)
    return result


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE",
                                            "PATCH", "HEAD", "OPTIONS"])
async def legacy_catch_all(request: Request, path: str = ""):
    return await _dispatch(request, '/' + path)
