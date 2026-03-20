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
Native FastAPI router for multireddit API endpoints.

Migrated from r2.controllers.multi (Phase D-3).

Route registration order matters: specific paths (/mine, /copy, /rename,
/user/{username}) must come before the greedy {multipath:path} catch-all,
and /r/{srname} + /description sub-paths must come before the base catch-all.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from r2.config.extensions import set_extension
from r2.controllers.reddit_base import abort_with_error
from r2.controllers.oauth2 import require_oauth2_scope
from r2.lib.context import c, response
from r2.lib.i18n import _
from r2.lib.jsontemplates import (
    LabeledMultiJsonTemplate,
    LabeledMultiDescriptionJsonTemplate,
)
from r2.lib.errors import RedditError
from r2.lib.validator import (
    validate,
    VAccountByName,
    VBoolean,
    VLength,
    VMarkdownLength,
    VModhash,
    VMultiPath,
    VOneOf,
    VSubredditName,
    VSRByName,
    VUser,
    VValidatedJSON,
    VColor,
)
from r2.models.account import Account
from r2.models.subreddit import (
    FakeSubreddit,
    LabeledMulti,
    LabeledMultiNotFound,
    Subreddit,
    TooManySubredditsError,
)

router = APIRouter()

# Error handler for JSON API endpoints: always abort with JSON error, never
# redirect (unlike the default handler which redirects USER_REQUIRED to /login).
def _api_error(error):
    abort_with_error(error, error.code or 400)


# ---------------------------------------------------------------------------
# JSON schema specs (module-level, shared across handlers)
# ---------------------------------------------------------------------------

multi_sr_data_json_spec = VValidatedJSON.Object({
    'name': VSubredditName('name', allow_language_srs=True),
})

MAX_DESC = 10000
MAX_DISP_NAME = 50
WRITABLE_MULTI_FIELDS = ('visibility', 'description_md', 'display_name',
                         'key_color', 'weighting_scheme')

multi_json_spec = VValidatedJSON.PartialObject({
    'description_md': VMarkdownLength('description_md', max_length=MAX_DESC,
                                      empty_error=None),
    'display_name': VLength('display_name', max_length=MAX_DISP_NAME),
    'icon_name': VOneOf('icon_name', lambda: __import__(
        'r2.lib.app_globals', fromlist=['g']).g.multi_icons + ("", None)),
    'key_color': VColor('key_color'),
    'visibility': VOneOf('visibility', ('private', 'public', 'hidden')),
    'weighting_scheme': VOneOf('weighting_scheme', ('classic', 'fresh')),
    'subreddits': VValidatedJSON.ArrayOf(multi_sr_data_json_spec),
})

multi_description_json_spec = VValidatedJSON.Object({
    'body_md': VMarkdownLength('body_md', max_length=MAX_DESC, empty_error=None),
})


# ---------------------------------------------------------------------------
# Helpers (module-level equivalents of the old class methods)
# ---------------------------------------------------------------------------

def _setup():
    """Set JSON extension/render_style for multi API requests."""
    set_extension("json")


def _format_multi_list(multis, viewer, expand_srs):
    templ = LabeledMultiJsonTemplate(expand_srs)
    return [templ.render(multi).finalize() for multi in multis
            if multi.can_view(viewer)]


def _format_multi(multi, expand_srs=False):
    return LabeledMultiJsonTemplate(expand_srs).render(multi).finalize()


def _format_multi_description(multi):
    return LabeledMultiDescriptionJsonTemplate().render(multi).finalize()


def _get_multi_subreddit(multi, sr):
    return LabeledMultiJsonTemplate.sr_props(multi, [sr])[0]


async def _fetch_multi(path_info, require_edit=False, kinds=None):
    """Look up a LabeledMulti by path and enforce view/edit permissions."""
    try:
        multi = await LabeledMulti._byID(path_info['path'])
    except LabeledMultiNotFound:
        raise RedditError('MULTI_NOT_FOUND', code=404)

    if kinds and multi.kind not in kinds:
        raise RedditError('MULTI_NOT_FOUND', code=404)
    if not multi.can_view(c.user):
        raise RedditError('MULTI_NOT_FOUND', code=404)
    if require_edit and not multi.can_edit(c.user):
        raise RedditError('MULTI_CANNOT_EDIT', code=403)
    return multi


def _check_new_multi_path(path_info):
    if path_info['owner'].lower() != c.user.name.lower():
        raise RedditError('MULTI_CANNOT_EDIT', code=403, fields='multipath')
    return c.user


async def _add_multi_srs(multi, sr_datas):
    srs = await Subreddit._by_name(sr_data['name'] for sr_data in sr_datas)

    for sr in srs.values():
        if isinstance(sr, FakeSubreddit):
            raise RedditError('MULTI_SPECIAL_SUBREDDIT',
                              msg_params={'path': sr.path},
                              code=400)

    sr_props = {}
    for sr_data in sr_datas:
        try:
            sr = srs[sr_data['name']]
        except KeyError:
            raise RedditError('SUBREDDIT_NOEXIST', code=400)
        else:
            del sr_data['name']
            sr_props[sr] = sr_data

    try:
        multi.add_srs(sr_props)
    except TooManySubredditsError:
        raise RedditError('MULTI_TOO_MANY_SUBREDDITS', code=409)

    return sr_props


async def _write_multi_data(multi, data):
    srs = data.pop('subreddits', None)
    if srs is not None:
        multi.clear_srs()
        try:
            await _add_multi_srs(multi, srs)
        except Exception:
            multi._revert()
            raise

    if 'icon_name' in data:
        try:
            multi.set_icon_by_name(data.pop('icon_name'))
        except Exception:
            multi._revert()
            raise

    for key, val in data.items():
        if key in WRITABLE_MULTI_FIELDS:
            setattr(multi, key, val)

    await multi._commit()
    return multi


async def _copy_multi(from_multi, to_path_info, rename=False):
    to_owner = _check_new_multi_path(to_path_info)

    if rename and from_multi.owner != to_owner:
        raise RedditError('MULTI_CANNOT_EDIT', code=400)

    try:
        await LabeledMulti._byID(to_path_info['path'])
    except LabeledMultiNotFound:
        to_multi = LabeledMulti.copy(to_path_info['path'], from_multi,
                                     owner=to_owner)
    else:
        raise RedditError('MULTI_EXISTS', code=409, fields='multipath')

    return to_multi


# ---------------------------------------------------------------------------
# Routes — specific paths before greedy {multipath:path} catch-alls
# ---------------------------------------------------------------------------

@router.get("/api/multi/mine")
@require_oauth2_scope("read")
@validate(VUser(), expand_srs=VBoolean("expand_srs"), _on_error=_api_error)
async def GET_my_multis(expand_srs=None):
    """Fetch a list of multis belonging to the current user."""
    _setup()
    multis = await LabeledMulti.by_owner(c.user)
    return JSONResponse(_format_multi_list(multis, c.user, expand_srs))


@router.get("/api/multi/user/{username}")
@require_oauth2_scope("read")
@validate(
    user=VAccountByName("username"),
    expand_srs=VBoolean("expand_srs"),
    _on_error=_api_error,
)
async def GET_list_multis(username: str, user=None, expand_srs=None):
    """Fetch a list of public multis belonging to `username`."""
    _setup()
    multis = await LabeledMulti.by_owner(user)
    return JSONResponse(_format_multi_list(multis, c.user, expand_srs))


@router.post("/api/multi/copy")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    from_path_info=VMultiPath("from", kinds='m'),
    to_path_info=VMultiPath("to", required=False,
        docs={"to": "destination multireddit url path"},
    ),
    display_name=VLength("display_name", max_length=MAX_DISP_NAME,
                         empty_error=None),
    _on_error=_api_error,
)
async def POST_multi_copy(from_path_info=None, to_path_info=None,
                          display_name=None):
    """Copy a multi. Responds with 409 Conflict if the target already exists."""
    _setup()
    from_multi = await _fetch_multi(from_path_info, kinds=('m',))

    if not to_path_info:
        if display_name:
            path = LabeledMulti.slugify(from_multi.owner, display_name)
            to_path_info = VMultiPath("").run(path)
        else:
            raise RedditError('BAD_MULTI_PATH', code=400)

    to_multi = await _copy_multi(from_multi, to_path_info)

    from_path = from_multi.path
    to_multi.copied_from = from_path
    if to_multi.description_md:
        to_multi.description_md += '\n\n'
    to_multi.description_md += _('copied from %(source)s') % {
        'source': f'[{from_path}]({from_path})'
    }
    to_multi.visibility = 'private'
    if display_name:
        to_multi.display_name = display_name
    await to_multi._commit()

    return JSONResponse(_format_multi(to_multi))


@router.post("/api/multi/rename")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    from_path_info=VMultiPath("from", kinds='m'),
    to_path_info=VMultiPath("to", required=False,
        docs={"to": "destination multireddit url path"},
    ),
    display_name=VLength("display_name", max_length=MAX_DISP_NAME,
                         empty_error=None),
    _on_error=_api_error,
)
async def POST_multi_rename(from_path_info=None, to_path_info=None,
                            display_name=None):
    """Rename a multi."""
    _setup()
    from_multi = await _fetch_multi(from_path_info, require_edit=True,
                                    kinds=('m',))

    if not to_path_info:
        if display_name:
            path = LabeledMulti.slugify(from_multi.owner, display_name)
            to_path_info = VMultiPath("").run(path)
        else:
            raise RedditError('BAD_MULTI_PATH', code=400)

    to_multi = await _copy_multi(from_multi, to_path_info, rename=True)

    if display_name:
        to_multi.display_name = display_name
        await to_multi._commit()
    await from_multi._commit_delete()

    return JSONResponse(_format_multi(to_multi))


@router.post("/api/multi")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath", required=False),
    data=VValidatedJSON("model", multi_json_spec),
    _on_error=_api_error,
)
async def POST_multi(path_info=None, data=None):
    """Create a multi. Responds with 409 Conflict if it already exists."""
    _setup()
    if not path_info and data and "path" in data:
        path_info = VMultiPath("").run(data["path"])
    elif data and 'display_name' in data:
        path = LabeledMulti.slugify(c.user, data['display_name'])
        path_info = VMultiPath("").run(path)

    if not path_info:
        raise RedditError('BAD_MULTI_PATH', code=400)

    _check_new_multi_path(path_info)

    try:
        await LabeledMulti._byID(path_info['path'])
    except LabeledMultiNotFound:
        multi = LabeledMulti.create(path_info['path'], c.user)
        status_code = 201
    else:
        raise RedditError('MULTI_EXISTS', code=409, fields='multipath')

    await _write_multi_data(multi, data)
    return JSONResponse(_format_multi(multi), status_code=status_code)


# --- /api/multi/{multipath:path}/r/{srname} before /api/multi/{multipath:path}

@router.get("/api/multi/{multipath:path}/r/{srname}")
@require_oauth2_scope("read")
@validate(
    VUser(),
    path_info=VMultiPath("multipath"),
    sr=VSRByName('srname'),
    _on_error=_api_error,
)
async def GET_multi_subreddit(multipath: str, srname: str,
                              path_info=None, sr=None):
    """Get data about a subreddit in a multi."""
    _setup()
    multi = await _fetch_multi(path_info)
    return JSONResponse(_get_multi_subreddit(multi, sr))


@router.put("/api/multi/{multipath:path}/r/{srname}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    sr_name=VSubredditName('srname', allow_language_srs=True),
    data=VValidatedJSON("model", multi_sr_data_json_spec),
    _on_error=_api_error,
)
async def PUT_multi_subreddit(multipath: str, srname: str,
                              path_info=None, sr_name=None, data=None):
    """Add a subreddit to a multi."""
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True)

    new = not any(sr.name.lower() == sr_name.lower() for sr in multi.srs)

    data['name'] = sr_name
    sr_props = await _add_multi_srs(multi, [data])
    sr = list(sr_props.items())[0][0]
    await multi._commit()

    status_code = 201 if new else 200
    return JSONResponse(_get_multi_subreddit(multi, sr), status_code=status_code)


@router.delete("/api/multi/{multipath:path}/r/{srname}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    sr=VSRByName('srname'),
    _on_error=_api_error,
)
async def DELETE_multi_subreddit(multipath: str, srname: str,
                                 path_info=None, sr=None):
    """Remove a subreddit from a multi."""
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True)
    multi.del_srs(sr)
    await multi._commit()
    return JSONResponse({})


# /api/filter/{multipath:path}/r/{srname}
@router.get("/api/filter/{multipath:path}/r/{srname}")
@require_oauth2_scope("read")
@validate(
    VUser(),
    path_info=VMultiPath("multipath"),
    sr=VSRByName('srname'),
    _on_error=_api_error,
)
async def GET_filter_subreddit(multipath: str, srname: str,
                               path_info=None, sr=None):
    _setup()
    multi = await _fetch_multi(path_info)
    return JSONResponse(_get_multi_subreddit(multi, sr))


@router.put("/api/filter/{multipath:path}/r/{srname}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    sr_name=VSubredditName('srname', allow_language_srs=True),
    data=VValidatedJSON("model", multi_sr_data_json_spec),
    _on_error=_api_error,
)
async def PUT_filter_subreddit(multipath: str, srname: str,
                               path_info=None, sr_name=None, data=None):
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True)
    new = not any(sr.name.lower() == sr_name.lower() for sr in multi.srs)
    data['name'] = sr_name
    sr_props = await _add_multi_srs(multi, [data])
    sr = list(sr_props.items())[0][0]
    await multi._commit()
    status_code = 201 if new else 200
    return JSONResponse(_get_multi_subreddit(multi, sr), status_code=status_code)


@router.delete("/api/filter/{multipath:path}/r/{srname}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    sr=VSRByName('srname'),
    _on_error=_api_error,
)
async def DELETE_filter_subreddit(multipath: str, srname: str,
                                  path_info=None, sr=None):
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True)
    multi.del_srs(sr)
    await multi._commit()
    return JSONResponse({})


# --- /api/multi/{multipath:path}/description before /api/multi/{multipath:path}

@router.get("/api/multi/{multipath:path}/description")
@require_oauth2_scope("read")
@validate(
    VUser(),
    path_info=VMultiPath("multipath", kinds='m'),
    _on_error=_api_error,
)
async def GET_multi_description(multipath: str, path_info=None):
    """Get a multi's description."""
    _setup()
    multi = await _fetch_multi(path_info, kinds=('m',))
    return JSONResponse(_format_multi_description(multi))


@router.put("/api/multi/{multipath:path}/description")
@require_oauth2_scope("read")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath", kinds='m'),
    data=VValidatedJSON('model', multi_description_json_spec),
    _on_error=_api_error,
)
async def PUT_multi_description(multipath: str, path_info=None, data=None):
    """Change a multi's markdown description."""
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True, kinds=('m',))
    multi.description_md = data['body_md']
    await multi._commit()
    return JSONResponse(_format_multi_description(multi))


# --- /api/multi/{multipath:path} catch-all (GET, PUT, DELETE)

@router.get("/api/multi/{multipath:path}")
@require_oauth2_scope("read")
@validate(
    path_info=VMultiPath("multipath"),
    expand_srs=VBoolean("expand_srs"),
    _on_error=_api_error,
)
async def GET_multi(multipath: str, path_info=None, expand_srs=None):
    """Fetch a multi's data and subreddit list by name."""
    _setup()
    multi = await _fetch_multi(path_info)
    return JSONResponse(_format_multi(multi, expand_srs))


@router.put("/api/multi/{multipath:path}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    data=VValidatedJSON("model", multi_json_spec),
    _on_error=_api_error,
)
async def PUT_multi(multipath: str, path_info=None, data=None):
    """Create or update a multi."""
    _setup()
    _check_new_multi_path(path_info)

    try:
        multi = await LabeledMulti._byID(path_info['path'])
        status_code = 200
    except LabeledMultiNotFound:
        multi = LabeledMulti.create(path_info['path'], c.user)
        status_code = 201

    await _write_multi_data(multi, data)
    return JSONResponse(_format_multi(multi), status_code=status_code)


@router.delete("/api/multi/{multipath:path}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    _on_error=_api_error,
)
async def DELETE_multi(multipath: str, path_info=None):
    """Delete a multi."""
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True)
    await multi._commit_delete()
    return JSONResponse({})


# --- /api/filter/{multipath:path} catch-all (GET, PUT, DELETE)

@router.get("/api/filter/{multipath:path}")
@require_oauth2_scope("read")
@validate(
    path_info=VMultiPath("multipath"),
    expand_srs=VBoolean("expand_srs"),
    _on_error=_api_error,
)
async def GET_filter(multipath: str, path_info=None, expand_srs=None):
    _setup()
    multi = await _fetch_multi(path_info)
    return JSONResponse(_format_multi(multi, expand_srs))


@router.put("/api/filter/{multipath:path}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    data=VValidatedJSON("model", multi_json_spec),
    _on_error=_api_error,
)
async def PUT_filter(multipath: str, path_info=None, data=None):
    _setup()
    _check_new_multi_path(path_info)

    try:
        multi = await LabeledMulti._byID(path_info['path'])
        status_code = 200
    except LabeledMultiNotFound:
        multi = LabeledMulti.create(path_info['path'], c.user)
        status_code = 201

    await _write_multi_data(multi, data)
    return JSONResponse(_format_multi(multi), status_code=status_code)


@router.delete("/api/filter/{multipath:path}")
@require_oauth2_scope("subscribe")
@validate(
    VUser(),
    VModhash(),
    path_info=VMultiPath("multipath"),
    _on_error=_api_error,
)
async def DELETE_filter(multipath: str, path_info=None):
    _setup()
    multi = await _fetch_multi(path_info, require_edit=True)
    await multi._commit_delete()
    return JSONResponse({})
