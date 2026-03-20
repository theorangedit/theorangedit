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
Native FastAPI router for button/widget embed endpoints.

Migrated from r2.controllers.buttons (Phase D-3).
"""

from fastapi import APIRouter
from starlette.responses import RedirectResponse, Response

from r2.lib.app_globals import g
from r2.lib.context import c, request
from r2.lib.i18n import _
from r2.lib.pages import ButtonLite, ButtonDemoPanel, WidgetDemoPanel, BoringPage
from r2.lib.pages.things import wrap_links
from r2.lib.validator import validate, VInt, VSanitizedUrl, VBoolean, nop
from r2.controllers.reddit_base import UnloggedUser
from r2.models import Link, FakeSubreddit, DomainSR, NotFound

router = APIRouter()


def _get_wrapped_link(url, link=None, wrapper=None):
    """Return the highest-scored wrapped Link for a URL, or None."""
    try:
        links = []
        if link:
            links = [link]
        else:
            sr = None if isinstance(c.site, FakeSubreddit) else c.site
            try:
                links = Link._by_url(url, sr)
            except NotFound:
                pass

        if links:
            if wrapper:
                links = wrap_links(links, wrapper=wrapper)
            else:
                links = wrap_links(links)
            links = list(links)
            links = max(links, key=lambda x: x._score) if links else None

        if not links and wrapper:
            return wrapper(None)
        return links
    except Exception:
        import traceback
        g.log.debug("FULLPATH: get_link error in buttons code")
        g.log.debug(traceback.format_exc())
        if wrapper:
            return wrapper(None)


@router.get("/button")
@validate(buttontype=VInt('t', 1, 5))
async def GET_button_embed(buttontype=None):
    if not buttontype:
        from r2.lib.base import abort
        abort(404)
    return RedirectResponse(
        url=f'/static/button/button{buttontype}.js',
        status_code=301,
    )


@router.get("/buttonlite")
@validate(
    buttonimage=VInt('i', 0, 14),
    title=nop('title'),
    url=VSanitizedUrl('url'),
    newwindow=VBoolean('newwindow', default=False),
    styled=VBoolean('styled', default=True),
)
async def GET_button_lite(buttonimage=None, title=None, url=None,
                          styled=True, newwindow=False):
    c.user = UnloggedUser([c.lang])
    c.user_is_loggedin = False
    c.render_style = 'js'

    if not url:
        url = request.headers.get('referer')

    def builder_wrapper(thing=None):
        kw = {}
        if not thing:
            kw['url'] = url
            kw['title'] = title
        return ButtonLite(
            thing,
            image=1 if buttonimage is None else buttonimage,
            target="_new" if newwindow else "_parent",
            styled=styled,
            **kw,
        )

    bjs = _get_wrapped_link(url, wrapper=builder_wrapper)
    return Response(content=bjs.render(), media_type="text/javascript")


@router.get("/buttons")
async def GET_button_demo_page():
    if isinstance(c.site, DomainSR):
        return RedirectResponse(url='/buttons', status_code=302)
    return Response(
        content=BoringPage(
            _("reddit buttons"),
            show_sidebar=False,
            content=ButtonDemoPanel(),
        ).render(),
        media_type='text/html; charset=UTF-8',
    )


@router.get("/widget")
async def GET_widget_demo_page():
    return Response(
        content=BoringPage(
            _("reddit widget"),
            show_sidebar=False,
            content=WidgetDemoPanel(),
        ).render(),
        media_type='text/html; charset=UTF-8',
    )
