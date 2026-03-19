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
from datetime import timedelta

_PREFIX = 'automod_performed_'
# Keep deduplication data for 90 days (automod rules rarely need longer)
_TTL = int(timedelta(days=90).total_seconds())


class PerformedRulesByThing:
    """Tracks which non-repeatable automod rules have been applied to a thing.

    Backed by g.permacache. Data is ephemeral — if lost, a non-repeatable rule
    may fire once more, which is an acceptable edge case.

    Replaces the old Cassandra-backed implementation.
    """

    @classmethod
    def _rowkey(cls, thing):
        return thing._fullname

    @classmethod
    def _cache_key(cls, thing):
        return _PREFIX + thing._fullname

    @classmethod
    def mark_performed(cls, thing, rule):
        from r2.lib.app_globals import g
        key = cls._cache_key(thing)
        already = cls.get_already_performed(thing)
        already.add(rule.unique_id)
        g.permacache.set(key, json.dumps(list(already)), time=_TTL)

    @classmethod
    def get_already_performed(cls, thing):
        from r2.lib.app_globals import g
        key = cls._cache_key(thing)
        raw = g.permacache.get(key)
        if not raw:
            return set()
        try:
            return set(json.loads(raw))
        except (ValueError, TypeError):
            return set()
