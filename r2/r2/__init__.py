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

"""r2

Entry point for the theorangedit application.

The ASGI app is exposed via r2.main:app (for uvicorn / gunicorn).
The make_app() factory is retained for backwards-compatibility with any
tooling that still calls it.
"""

# Pre-import _strptime to avoid threading issues with simultaneous imports
# (see https://code.google.com/p/modwsgi/wiki/ApplicationIssues)
import _strptime  # noqa: F401


def make_app(*args, **kwargs):
    """Return the configured ASGI application."""
    from r2.config.middleware import make_app as real_make_app
    return real_make_app(*args, **kwargs)
