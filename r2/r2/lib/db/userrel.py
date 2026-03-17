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
userrel.py — compatibility stub.

UserRel/MigratingUserRel have been replaced by the subreddit relations tables
(SubredditModerator, SubredditContributor, SubredditBanned, etc.) in the new
ORM schema. This module is a stub.
"""


class CreationError(Exception):
    pass


class UserRel:
    """Legacy UserRel — stub. Use subreddit relation tables via service layer."""

    @classmethod
    def rel(cls, *args, **kwargs):
        raise NotImplementedError(
            "UserRel.rel: replaced by subreddit relation tables. Use r2.services.subreddits."
        )


class MigratingUserRel(UserRel):
    pass
