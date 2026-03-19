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

import json
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


_FB_PREFIX = 'sr_feedback_'
_ES_PREFIX = 'explore_settings_'


class AccountSRFeedback:
    """Per-user SR recommendation feedback backed by g.permacache.

    Stores lists of (sr_id36, timestamp) pairs per action type.
    Expired entries are filtered on read according to FEEDBACK_TTL.

    Replaces the old Cassandra-backed implementation.
    """

    @classmethod
    def _key(cls, account, action):
        return f'{_FB_PREFIX}{account._id}_{action}'

    @classmethod
    def _read_entries(cls, account, action):
        """Return a list of (sr_id36, timestamp) for the given action, filtering expired."""
        raw = g.permacache.get(cls._key(account, action))
        if not raw:
            return []
        try:
            entries = json.loads(raw)
        except (ValueError, TypeError):
            return []
        ttl = FEEDBACK_TTL.get(action, 0)
        if ttl:
            cutoff = time.time() - ttl
            entries = [e for e in entries if e[1] >= cutoff]
        return entries

    @classmethod
    def _write_entries(cls, account, action, entries):
        ttl = int(FEEDBACK_TTL.get(action, 0))
        g.permacache.set(cls._key(account, action), json.dumps(entries),
                         time=ttl or 0)

    @classmethod
    def for_user(cls, account):
        """Return {action: set_of_sr_id36} for all FEEDBACK_ACTIONS."""
        result = {action: set() for action in FEEDBACK_ACTIONS}
        for action in FEEDBACK_ACTIONS:
            entries = cls._read_entries(account, action)
            result[action] = {e[0] for e in entries}
        return result

    @classmethod
    def record_feedback(cls, account, srs, action):
        """Record that the user took ``action`` on each sr in ``srs``."""
        if action not in FEEDBACK_ACTIONS:
            return
        now = time.time()
        existing = cls._read_entries(account, action)
        existing_ids = {e[0] for e in existing}
        for sr in srs:
            sr_id36 = sr._id36
            if sr_id36 not in existing_ids:
                existing.append([sr_id36, now])
        cls._write_entries(account, action, existing)

    @classmethod
    def record_views(cls, account, sr_data):
        """Record VIEW feedback for each sr in ``sr_data`` (a {sr: src} dict)."""
        cls.record_feedback(account, sr_data.keys(), VIEW)


class ExploreSettings:
    """Explore page user settings backed by g.permacache.

    Replaces the old Cassandra-backed implementation.
    """

    @classmethod
    def _key(cls, account):
        return f'{_ES_PREFIX}{account._id}'

    @classmethod
    def for_user(cls, account):
        """Return an ExploreSettings-like object for the given user."""
        raw = g.permacache.get(cls._key(account))
        if not raw:
            return DefaultExploreSettings()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return DefaultExploreSettings()
        settings = DefaultExploreSettings()
        settings.personalized = data.get('personalized', True)
        settings.discovery = data.get('discovery', True)
        settings.rising = data.get('rising', True)
        settings.nsfw = data.get('nsfw', False)
        return settings

    @classmethod
    def record_settings(cls, user, personalized=False, discovery=False,
                        rising=False, nsfw=False):
        data = {
            'personalized': personalized,
            'discovery': discovery,
            'rising': rising,
            'nsfw': nsfw,
        }
        g.permacache.set(cls._key(user), json.dumps(data))


class DefaultExploreSettings(object):
    """Default values to use when no settings have been saved for the user."""
    def __init__(self):
        self.personalized = True
        self.discovery = True
        self.rising = True
        self.nsfw = False
