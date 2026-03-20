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
Native FastAPI router for embed/blog endpoints.

Migrated from r2.controllers.embed (Phase D-3).
Only GET /blog is routed — the old GET_help/POST_help/GET_faq methods were
unreachable (help → wiki controller, faq → redirect controller).
"""

from fastapi import APIRouter
from starlette.responses import RedirectResponse

from r2.lib.template_helpers import get_domain

router = APIRouter()


@router.get("/blog")
async def GET_blog():
    return RedirectResponse(
        url=f"https://blog.{get_domain(subreddit=False, no_www=True)}/",
        status_code=302,
    )
