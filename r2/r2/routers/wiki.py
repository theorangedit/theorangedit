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
Wiki and WikiApi endpoints — Phase D-3 migration.

Migrated from:
  r2.controllers.wiki.WikiController    → /wiki/* and /help/* routes
  r2.controllers.wiki.WikiApiController → /api/wiki/* routes

Naming convention for route handlers
-------------------------------------
Routes with a ``{page:path}`` path parameter use ``page: str`` for the raw
URL segment (injected by FastAPI) and a *different* name for the @validate
result so the two don't collide after ``build_arg_list`` + validator merging:

  page: str          — raw path segment, e.g. "config/stylesheet"
  wiki_page          — validated WikiPage ORM object
  page_name          — validated/normalised page name string (from VWikiPageName)
  wp                 — VWikiPageRevise result (tuple of WikiPage, previous)
  pv                 — VWikiPageAndVersion result (page, v, v2)
"""

import json

from fastapi import APIRouter
from fastapi.responses import Response, RedirectResponse

from r2.lib.context import request
from r2.lib.context import c
from r2.lib.app_globals import g

from r2.controllers.reddit_base import abort_with_error
from r2.lib.utils import url_links_builder
from r2.models.wiki import (
    ContentLengthError,
    modactions,
    WikiPage,
    WikiPageExists,
    WikiRevision,
)
from r2.models.subreddit import DefaultSR
from r2.models.modaction import ModAction
from r2.models.builder import WikiRevisionBuilder, WikiRecentRevisionBuilder

from r2.lib.template_helpers import join_urls
from r2.lib.validator import (
    nop,
    validate,
    VAdmin,
    VBoolean,
    VExistingUname,
    VInt,
    VMarkdown,
    VModhash,
    VNotInTimeout,
    VOneOf,
    VPrintable,
    VRatelimit,
)
from r2.lib.validator.wiki import (
    VWikiPage,
    VWikiPageAndVersion,
    VWikiModerator,
    VWikiPageRevise,
    this_may_revise,
    this_may_view,
    VWikiPageName,
)
from r2.lib.pages.wiki import (WikiPageView, WikiNotFound, WikiRevisions,
                               WikiEdit, WikiSettings, WikiRecent,
                               WikiListing, WikiDiscussions,
                               WikiCreate)
from r2.config.extensions import set_extension
from r2.lib.template_helpers import add_sr
from r2.models.listing import WikiRevisionListing
from r2.lib.pages.things import default_thing_wrapper
from r2.lib.pages import BoringPage, CssError
from r2.models import IDBuilder, LinkListing, DefaultSR
from r2.lib.merge import ConflictException, make_htmldiff
from r2.lib.i18n import _
from r2.lib.utils import timesince
from r2.config import extensions
from r2.lib.base import abort
from r2.lib.errors import reddit_http_error
from r2.lib.automoderator import Ruleset

router = APIRouter()

page_descriptions = {
    "config/stylesheet": _("This page is the subreddit stylesheet, changes here apply to the subreddit css"),
    "config/submit_text": _("The contents of this page appear on the submit page"),
    "config/sidebar": _("The contents of this page appear on the subreddit sidebar"),
    "config/description": _("The contents of this page appear in the public subreddit description and when the user does not have access to the subreddit"),
    "config/automoderator": _("This page is used to configure AutoModerator for the subreddit, please see [the full documentation](/wiki/automoderator/full-documentation) for information"),
}

ATTRIBUTE_BY_PAGE = {"config/sidebar": "description",
                     "config/submit_text": "submit_text",
                     "config/description": "public_description"}
RENDERERS_BY_PAGE = {
    "config/automoderator": "automoderator",
    "config/description": "reddit",
    "config/sidebar": "reddit",
    "config/stylesheet": "stylesheet",
    "config/submit_text": "reddit",
    "toolbox": "rawcode",
    "usernotes": "rawcode",
}


# ---------------------------------------------------------------------------
# Setup helpers (replaces WikiController.pre / WikiApiController.pre)
# ---------------------------------------------------------------------------

def _handle_wiki_error(code, reason=None, **data):
    """Abort with a Reddit-style HTTP error response."""
    abort(reddit_http_error(code, reason, **data))


def _setup_wiki():
    """Run wiki access checks and populate wiki context vars.

    Migrated from WikiController.pre().  Must be called at the start of
    every wiki frontend handler.
    """
    if g.disable_wiki and not c.user_is_admin:
        _handle_wiki_error(403, 'WIKI_DOWN')
    if not c.site._should_wiki:
        _handle_wiki_error(404, 'NOT_WIKIABLE')
    frontpage = isinstance(c.site, DefaultSR)
    c.wiki_base_url = join_urls(c.site.path, 'wiki')
    c.wiki_api_url = join_urls(c.site.path, '/api/wiki')
    c.wiki_id = g.default_sr if frontpage else c.site.name
    c.is_wiki_mod = (
        c.user_is_admin or c.site.is_moderator_with_perms(c.user, 'wiki')
    ) if c.user_is_loggedin else False
    c.wikidisabled = False
    mode = c.site.wikimode
    if not mode or mode == 'disabled':
        if not c.is_wiki_mod:
            _handle_wiki_error(403, 'WIKI_DISABLED')
        else:
            c.wikidisabled = True


def _setup_wiki_api():
    """Setup for WikiApi (JSON API) endpoints.

    Migrated from WikiApiController.pre().
    """
    _setup_wiki()
    c.render_style = 'api'
    set_extension('json')


def _wiki_on_error(error):
    """@validate _on_error for wiki endpoints — always abort with error code."""
    abort_with_error(error, error.code or 400)


# ---------------------------------------------------------------------------
# Wiki API routes: POST /api/wiki/*
# Registered first so they take precedence over frontend /wiki/* routes.
# ---------------------------------------------------------------------------

@router.post("/api/wiki/edit")
@validate(VModhash(),
          pageandprevious=VWikiPageRevise(('page', 'previous'), restricted=True),
          content=nop('content'),
          page_name=VWikiPageName('page'),
          reason=VPrintable('reason', 256, empty_error=None),
          _on_error=_wiki_on_error)
async def POST_wiki_edit(pageandprevious=None, content=None, page_name=None,
                         reason=None):
    """Edit a wiki page."""
    _setup_wiki_api()
    page_obj, previous = pageandprevious

    if c.user._spam:
        error = _("You are doing that too much, please try again later.")
        _handle_wiki_error(415, 'SPECIAL_ERRORS', special_errors=[error])

    if not page_obj:
        error = c.errors.get(('WIKI_CREATE_ERROR', 'page'))
        if error:
            _handle_wiki_error(403, **(error.msg_params or {}))
        VNotInTimeout().run(action_name="wikirevise", details_text="create")
        try:
            page_obj = WikiPage.create(c.site, page_name)
        except WikiPageExists:
            _handle_wiki_error(400, 'WIKI_CREATE_ERROR')
    else:
        VNotInTimeout().run(action_name="wikirevise", details_text="edit",
                            target=page_obj)
        error = c.errors.get(('MAY_NOT_REVISE', 'page'))
        if error:
            _handle_wiki_error(403, **(error.msg_params or {}))

    renderer = RENDERERS_BY_PAGE.get(page_obj.name, 'wiki')
    if renderer in ('wiki', 'reddit'):
        content = VMarkdown('content', renderer=renderer).run(content)

    # Use the raw POST value to distinguish None/Undefined from empty string.
    _form = getattr(request.state, '_form_data', {})
    previous = previous._id if previous else _form.get('previous')
    try:
        if page_obj.name == 'config/stylesheet':
            css_errors, parsed = c.site.parse_css(content, verify=False)
            if g.css_killswitch:
                _handle_wiki_error(403, 'STYLESHEET_EDIT_DENIED')
            if css_errors:
                error_items = [CssError(x).message for x in css_errors]
                _handle_wiki_error(415, 'SPECIAL_ERRORS', special_errors=error_items)
        elif page_obj.name == "config/automoderator":
            try:
                Ruleset(content)
            except ValueError as e:
                _handle_wiki_error(415, "SPECIAL_ERRORS", special_errors=[e.message])

        if page_obj.name == "config/stylesheet":
            c.site.change_css(content, parsed, previous, reason=reason)
        else:
            try:
                page_obj.revise(content, previous, c.user._id36, reason=reason)
            except ContentLengthError as e:
                _handle_wiki_error(403, 'CONTENT_LENGTH_ERROR',
                                   max_length=e.max_length)
            if page_obj.special and page_obj.name in ATTRIBUTE_BY_PAGE:
                setattr(c.site, ATTRIBUTE_BY_PAGE[page_obj.name], content)
                await c.site._commit()
            if page_obj.special or c.is_wiki_mod:
                description = modactions.get(page_obj.name,
                                             'Page %s edited' % page_obj.name)
                ModAction.create(c.site, c.user, "wikirevise",
                                 details=description, description=reason)
    except ConflictException as e:
        _handle_wiki_error(409, 'EDIT_CONFLICT', newcontent=e.new,
                           newrevision=page_obj.revision,
                           diffcontent=e.htmldiff)
    return Response(content=json.dumps({}), media_type="application/json")


@router.post("/api/wiki/alloweditor/{act}")
@validate(VModhash(),
          VWikiModerator(),
          wiki_page=VWikiPage('page'),
          user=VExistingUname('username'),
          _on_error=_wiki_on_error)
def POST_wiki_allow_editor(act: str, wiki_page=None, user=None):
    """Allow/deny username to edit this wiki page."""
    _setup_wiki_api()
    if not user:
        _handle_wiki_error(404, 'UNKNOWN_USER')
    elif act == 'del':
        VNotInTimeout().run(action_name="wikipermlevel",
                            details_text="del_editor", target=user)
        wiki_page.remove_editor(user._id36)
    elif act == 'add':
        VNotInTimeout().run(action_name="wikipermlevel",
                            details_text="allow_editor", target=user)
        wiki_page.add_editor(user._id36)
    else:
        _handle_wiki_error(400, 'INVALID_ACTION')
    return Response(content=json.dumps({}), media_type="application/json")


@router.post("/api/wiki/hide")
@validate(VModhash(),
          VWikiModerator(),
          pv=VWikiPageAndVersion(('page', 'revision')),
          _on_error=_wiki_on_error)
def POST_wiki_revision_hide(pv=None):
    """Toggle the public visibility of a wiki page revision."""
    _setup_wiki_api()
    page_obj, revision = pv
    if not revision:
        _handle_wiki_error(400, 'INVALID_REVISION')
    VNotInTimeout().run(action_name="wikirevise",
                        details_text="revision_hide", target=page_obj)
    return Response(content=json.dumps({'status': revision.toggle_hide()}),
                    media_type="application/json")


@router.post("/api/wiki/delete")
@validate(
    VModhash(),
    VAdmin(),
    pv=VWikiPageAndVersion(('page', 'revision')),
    deleted=VBoolean('deleted'),
    _on_error=_wiki_on_error,
)
async def POST_wiki_revision_delete(pv=None, deleted=None):
    """Admin: show/hide a wiki revision."""
    _setup_wiki_api()
    page_obj, revision = pv
    if not revision:
        _handle_wiki_error(400, 'INVALID_REVISION')
    if deleted and page_obj.revision == str(revision._id):
        _handle_wiki_error(400, 'REVISION_IS_CURRENT')
    revision.admin_deleted = deleted
    await revision._commit()
    return Response(content=json.dumps({'status': revision.admin_deleted}),
                    media_type="application/json")


@router.post("/api/wiki/revert")
@validate(VModhash(),
          VWikiModerator(),
          pv=VWikiPageAndVersion(('page', 'revision')),
          _on_error=_wiki_on_error)
async def POST_wiki_revision_revert(pv=None):
    """Revert a wiki page to a previous revision."""
    _setup_wiki_api()
    page_obj, revision = pv
    if not revision:
        _handle_wiki_error(400, 'INVALID_REVISION')
    VNotInTimeout().run(action_name="wikirevise",
                        details_text="revision_revert", target=page_obj)
    content = revision.content
    reason = 'reverted back %s' % timesince(revision.date)
    if page_obj.name == 'config/stylesheet':
        css_errors, parsed = c.site.parse_css(content)
        if css_errors:
            _handle_wiki_error(403, 'INVALID_CSS')
        c.site.change_css(content, parsed, prev=None, reason=reason, force=True)
    else:
        try:
            page_obj.revise(content, author=c.user._id36, reason=reason,
                            force=True)
            if page_obj.name in ATTRIBUTE_BY_PAGE:
                setattr(c.site, ATTRIBUTE_BY_PAGE[page_obj.name], content)
                await c.site._commit()
        except ContentLengthError as e:
            _handle_wiki_error(403, 'CONTENT_LENGTH_ERROR',
                               max_length=e.max_length)
    return Response(content=json.dumps({}), media_type="application/json")


# ---------------------------------------------------------------------------
# Wiki frontend routes: specific sub-paths before the wildcard /wiki/{page}
# ---------------------------------------------------------------------------

@router.get("/wiki/pages")
def GET_wiki_listing():
    """Retrieve a list of wiki pages in this subreddit."""
    _setup_wiki()

    def check_hidden(pg):
        return pg.listed and this_may_view(pg)

    pages, linear_pages = WikiPage.get_listing(c.site, filter_check=check_hidden)
    content = WikiListing(pages, linear_pages).render()
    return Response(content=content, media_type="text/html")


@router.get("/wiki/revisions")
def GET_wiki_recent():
    """Retrieve a list of recently changed wiki pages in this subreddit."""
    _setup_wiki()
    qs = request.query_params
    num = int(qs.get('limit', 25))
    after = qs.get('after')
    reverse = qs.get('show') == 'all'
    count = int(qs.get('count', 0))
    revisions = WikiRevision.get_recent(c.site)
    wikiuser = c.user if c.user_is_loggedin else None
    builder = WikiRecentRevisionBuilder(revisions, num=num, count=count,
                                        reverse=reverse, after=after,
                                        wrap=default_thing_wrapper(),
                                        skip=not c.is_wiki_mod,
                                        user=wikiuser, sr=c.site)
    listing = WikiRevisionListing(builder).listing()
    content = WikiRecent(listing).render()
    return Response(content=content, media_type="text/html")


@router.get("/wiki/create/{page:path}")
@validate(wp=VWikiPageRevise('page'),
          page_name=VWikiPageName('page'),
          _on_error=_wiki_on_error)
def GET_wiki_create(page: str = "", wp=None, page_name=None):
    """Show the wiki page creation form."""
    _setup_wiki()
    api = c.render_style in extensions.API_TYPES
    error = c.errors.get(('WIKI_CREATE_ERROR', 'page'))
    if error:
        error = error.msg_params
    if wp[0]:
        VNotInTimeout().run(action_name="wikirevise",
                            details_text="create", target=wp[0])
        return RedirectResponse(url=join_urls(c.wiki_base_url, wp[0].name),
                                status_code=302)
    elif api:
        if error:
            _handle_wiki_error(403, **error)
        else:
            _handle_wiki_error(404, 'PAGE_NOT_CREATED')
    elif error:
        error_msg = ''
        if error['reason'] == 'PAGE_NAME_LENGTH':
            error_msg = _("this wiki cannot handle page names of that magnitude!  please select a page name shorter than %d characters") % error['max_length']
        elif error['reason'] == 'PAGE_CREATED_ELSEWHERE':
            error_msg = _("this page is a special page, please go into the subreddit settings and save the field once to create this special page")
        elif error['reason'] == 'PAGE_NAME_MAX_SEPARATORS':
            error_msg = _('a max of %d separators "/" are allowed in a wiki page name.') % error['max_separators']
        content = BoringPage(_("Wiki error"), infotext=error_msg).render()
        return Response(content=content, media_type="text/html")
    else:
        VNotInTimeout().run(action_name="wikirevise", details_text="create")
        content = WikiCreate(page=page_name, may_revise=True).render()
        return Response(content=content, media_type="text/html")


@router.get("/wiki/edit/{page:path}")
@validate(wp=VWikiPageRevise('page', restricted=True, required=True),
          _on_error=_wiki_on_error)
def GET_wiki_revise(page: str = "", wp=None):
    """Show the wiki page editor."""
    _setup_wiki()
    page_obj = wp[0]
    VNotInTimeout().run(action_name="wikirevise", details_text="revise",
                        target=page_obj)
    error = c.errors.get(('MAY_NOT_REVISE', 'page'))
    if error:
        _handle_wiki_error(403, **(error.msg_params or {}))
    qs = request.query_params
    previous = qs.get('previous', page_obj._get('revision'))
    content_val = qs.get('content', page_obj.content)
    message = page_descriptions.get(page_obj.name)
    content = WikiEdit(content_val, previous, alert=message, page=page_obj.name,
                       may_revise=True).render()
    return Response(content=content, media_type="text/html")


@router.get("/wiki/revisions/{page:path}")
@validate(wiki_page=VWikiPage('page', restricted=False),
          _on_error=_wiki_on_error)
def GET_wiki_revisions(page: str = "", wiki_page=None):
    """Retrieve a list of revisions of a wiki page."""
    _setup_wiki()
    qs = request.query_params
    num = int(qs.get('limit', 25))
    after = qs.get('after')
    reverse = qs.get('show') == 'all'
    count = int(qs.get('count', 0))
    revisions = wiki_page.get_revisions()
    wikiuser = c.user if c.user_is_loggedin else None
    builder = WikiRevisionBuilder(revisions, user=wikiuser, sr=c.site,
                                  num=num, reverse=reverse, count=count,
                                  after=after, skip=not c.is_wiki_mod,
                                  wrap=default_thing_wrapper(),
                                  page=wiki_page)
    listing = WikiRevisionListing(builder).listing()
    content = WikiRevisions(listing, page=wiki_page.name,
                            may_revise=this_may_revise(wiki_page)).render()
    return Response(content=content, media_type="text/html")


def _render_wiki_settings(wiki_page):
    """Render wiki settings page — shared by GET and POST handlers."""
    settings = {'permlevel': wiki_page._get('permlevel', 0),
                'listed': wiki_page.listed}
    VNotInTimeout().run(action_name="pageview",
                        details_text="wikisettings", target=wiki_page)
    mayedit = wiki_page.get_editor_accounts()
    restricted = (not wiki_page.special) and wiki_page.restricted
    show_editors = not restricted
    return WikiSettings(settings, mayedit, show_settings=not wiki_page.special,
                        page=wiki_page.name, show_editors=show_editors,
                        restricted=restricted, may_revise=True).render()


@router.get("/wiki/settings/{page:path}")
@validate(wiki_page=VWikiPage('page', restricted=True, modonly=True),
          _on_error=_wiki_on_error)
def GET_wiki_settings(page: str = "", wiki_page=None):
    """Retrieve the current permission settings for a wiki page."""
    _setup_wiki()
    content = _render_wiki_settings(wiki_page)
    return Response(content=content, media_type="text/html")


@router.post("/wiki/settings/{page:path}")
@validate(
    VModhash(),
    wiki_page=VWikiPage('page', restricted=True, modonly=True),
    permlevel=VInt('permlevel'),
    listed=VBoolean('listed'),
    _on_error=_wiki_on_error,
)
async def POST_wiki_settings(page: str = "", wiki_page=None, permlevel=None,
                              listed=None):
    """Update the permissions and visibility of a wiki page."""
    _setup_wiki()
    oldpermlevel = wiki_page.permlevel
    if oldpermlevel != permlevel:
        VNotInTimeout().run(action_name="wikipermlevel",
                            details_text="edit", target=wiki_page)
    if wiki_page.listed != listed:
        VNotInTimeout().run(action_name="wikipagelisted",
                            details_text="edit", target=wiki_page)
    try:
        wiki_page.change_permlevel(permlevel)
    except ValueError:
        _handle_wiki_error(403, 'INVALID_PERMLEVEL')
    if wiki_page.listed != listed:
        wiki_page.listed = listed
        await wiki_page._commit()
        verb = 'Relisted' if listed else 'Delisted'
        description = '%s page %s' % (verb, wiki_page.name)
        ModAction.create(c.site, c.user, 'wikipagelisted',
                         description=description)
    if oldpermlevel != permlevel:
        description = 'Page: %s, Changed from %s to %s' % (
            wiki_page.name, oldpermlevel, permlevel
        )
        ModAction.create(c.site, c.user, 'wikipermlevel',
                         description=description)
    content = _render_wiki_settings(wiki_page)
    return Response(content=content, media_type="text/html")


@router.get("/wiki/discussions/{page:path}")
@validate(wiki_page=VWikiPage('page', restricted=True),
          _on_error=_wiki_on_error)
def GET_wiki_discussions(page: str = "", wiki_page=None):
    """Retrieve a list of discussions about a wiki page."""
    _setup_wiki()
    qs = request.query_params
    num = int(qs.get('limit', 25))
    after = qs.get('after')
    reverse = qs.get('show') == 'all'
    count = int(qs.get('count', 0))
    page_url = add_sr("%s/%s" % (c.wiki_base_url, wiki_page.name))
    builder = url_links_builder(page_url, num=num, after=after,
                                reverse=reverse, count=count)
    listing = LinkListing(builder).listing()
    content = WikiDiscussions(listing, page=wiki_page.name,
                              may_revise=this_may_revise(wiki_page)).render()
    return Response(content=content, media_type="text/html")


# ---------------------------------------------------------------------------
# Wiki page view — wildcard, must come AFTER all specific sub-paths
# ---------------------------------------------------------------------------

@router.get("/wiki/")
@router.get("/wiki/{page:path}")
@validate(pv=VWikiPageAndVersion(('page', 'v', 'v2'),
                                  required=False,
                                  restricted=False,
                                  allow_hidden_revision=False),
           page_name=VWikiPageName('page', error_on_name_normalized=True),
           _on_error=_wiki_on_error)
def GET_wiki_page(page: str = "", pv=None, page_name=None):
    """Return the content of a wiki page.

    If ``v`` is given, show the wiki page as it was at that version.
    If both ``v`` and ``v2`` are given, show a diff of the two.
    """
    _setup_wiki()

    if c.errors.get(('PAGE_NAME_NORMALIZED', 'page')):
        url = join_urls(c.wiki_base_url, page_name)
        return RedirectResponse(url=url, status_code=302)

    page_obj, version, version2 = pv

    if not page_obj:
        is_api = c.render_style in extensions.API_TYPES
        if this_may_revise():
            if is_api:
                _handle_wiki_error(404, 'PAGE_NOT_CREATED')
            errorpage = WikiNotFound(page=page_name)
            request.state.usable_error_content = errorpage.render()
        elif is_api:
            _handle_wiki_error(404, 'PAGE_NOT_FOUND')
        abort(404, "not found")

    if version:
        edit_by = version.get_author()
        edit_date = version.date
    else:
        edit_by = page_obj.get_author()
        edit_date = page_obj._get('last_edit_date')

    diffcontent = None
    if not version:
        content = page_obj.content
        message = None
        if c.is_wiki_mod and page_obj.name in page_descriptions:
            message = page_descriptions[page_obj.name]
    else:
        if version2:
            t1 = timesince(version.date)
            t2 = timesince(version2.date)
            timestamp1 = _("%s ago") % t1
            timestamp2 = _("%s ago") % t2
            message = _("comparing revisions from %(date_1)s and %(date_2)s") \
                      % {'date_1': t1, 'date_2': t2}
            diffcontent = make_htmldiff(version.content, version2.content,
                                        timestamp1, timestamp2)
            content = version2.content
        else:
            message = _("viewing revision from %s ago") % timesince(version.date)
            content = version.content

    renderer = RENDERERS_BY_PAGE.get(page_obj.name, 'wiki')
    page_content = WikiPageView(content, alert=message, v=version,
                                diff=diffcontent,
                                may_revise=this_may_revise(page_obj),
                                edit_by=edit_by,
                                edit_date=edit_date, page=page_obj.name,
                                renderer=renderer).render()
    return Response(content=page_content, media_type="text/html")


# ---------------------------------------------------------------------------
# Redirect helpers: /help, /help/*, /w/*
# ---------------------------------------------------------------------------

def _wiki_redirect(page='index'):
    """Redirect to the wiki equivalent of a /help/* or /w/* URL."""
    _setup_wiki()
    return RedirectResponse(url=str("%s/%s" % (c.wiki_base_url, page)),
                            status_code=301)


@router.get("/help")
def GET_help():
    """Redirect /help to the wiki index."""
    return _wiki_redirect()


@router.get("/help/{page:path}")
@router.get("/w/{page:path}")
def GET_wiki_redirect(page: str = 'index'):
    """Redirect /help/* and /w/* to the equivalent wiki page."""
    return _wiki_redirect(page=page)
