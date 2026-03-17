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
LastModified — replaces Cassandra-backed View with memcache.

Keys: "lastmod:{fullname}:{name}" → datetime
TTL: 7 days (same as old Cassandra TTL)
"""

import datetime
from r2.lib.app_globals import g
from r2.lib.utils import tup

_TTL = 7 * 24 * 3600  # 7 days in seconds


def _key(fullname, name):
    return 'lastmod:%s:%s' % (fullname, name)


class LastModified:
    @classmethod
    def touch(cls, fullname, names):
        names = tup(names)
        now = datetime.datetime.now(g.tz)
        cache = getattr(g, 'thingcache', None)
        if cache is not None:
            for name in names:
                cache.set(_key(fullname, name), now, time=_TTL)
        return now

    @classmethod
    def get(cls, fullname, name, touch_if_not_set=False):
        cache = getattr(g, 'thingcache', None)
        if cache is None:
            return None
        val = cache.get(_key(fullname, name))
        if val is None and touch_if_not_set:
            return cls.touch(fullname, name)
        return val

    @classmethod
    def get_multi(cls, fullnames, name):
        cache = getattr(g, 'thingcache', None)
        if cache is None:
            return {fn: None for fn in fullnames}
        keys = {fn: _key(fn, name) for fn in fullnames}
        raw = cache.get_multi(list(keys.values()))
        return {fn: raw.get(keys[fn]) for fn in fullnames}
