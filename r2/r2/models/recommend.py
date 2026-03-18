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

import time

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain
from r2.lib.app_globals import g

from r2.lib.utils import utils, tup
from r2.models import Account, LabeledMulti, Subreddit
from r2.lib.pages import ExploreItem

VIEW = 'imp'
CLICK = 'clk'
DISMISS = 'dis'
FEEDBACK_ACTIONS = [VIEW, CLICK, DISMISS]

# how long to keep each type of feedback
FEEDBACK_TTL = {VIEW: timedelta(hours=6).total_seconds(),  # link lifetime
                CLICK: timedelta(minutes=30).total_seconds(),  # one session
                DISMISS: timedelta(days=60).total_seconds()}  # two months


class AccountSRPrefs(object):
    """Class for managing user recommendation preferences.

    Builds a user profile on-the-fly based on the user's subscriptions,
    multireddits, and recent interactions with the recommender UI.

    Likes are used to generate recommendations, dislikes to filter out
    unwanted results, and recent views to make sure the same subreddits aren't
    recommended too often.

    """

    def __init__(self):
        self.likes = set()
        self.dislikes = set()
        self.recent_views = set()

    @classmethod
    def for_user(cls, account):
        """Return a new AccountSRPrefs obj populated with user's data."""
        prefs = cls()
        multis = LabeledMulti.by_owner(account)
        multi_srs = set(chain.from_iterable(multi.srs for multi in multis))
        feedback = AccountSRFeedback.for_user(account)
        # subscriptions and srs in the user's multis become likes
        subscriptions = Subreddit.user_subreddits(account, limit=None)
        prefs.likes.update(utils.to36(sr_id) for sr_id in subscriptions)
        prefs.likes.update(sr._id36 for sr in multi_srs)
        # recent clicks on explore tab items are also treated as likes
        prefs.likes.update(feedback[CLICK])
        # dismissed recommendations become dislikes
        prefs.dislikes.update(feedback[DISMISS])
        # dislikes take precedence over likes
        prefs.likes = prefs.likes.difference(prefs.dislikes)
        # recently recommended items won't be shown again right away
        prefs.recent_views.update(feedback[VIEW])
        return prefs


_MSG = 'Cassandra removed — re-implement with PostgreSQL'


class AccountSRFeedback:
    """Recommendation feedback — stub only, Cassandra backend removed."""

    @classmethod
    def for_user(cls, account):
        raise NotImplementedError(_MSG)

    @classmethod
    def record_feedback(cls, account, srs, action):
        raise NotImplementedError(_MSG)

    @classmethod
    def record_views(cls, account, srs):
        raise NotImplementedError(_MSG)


class ExploreSettings:
    """Explore page user settings — stub only, Cassandra backend removed."""

    @classmethod
    def for_user(cls, account):
        return DefaultExploreSettings()

    @classmethod
    def record_settings(cls, user, personalized=False, discovery=False,
                        rising=False, nsfw=False):
        raise NotImplementedError(_MSG)


class DefaultExploreSettings(object):
    """Default values to use when no settings have been saved for the user."""
    def __init__(self):
        self.personalized = True
        self.discovery = True
        self.rising = True
        self.nsfw = False
