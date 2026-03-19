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

NoDefault = object()

_PREFIX = 'named_globals_'
_TTL = 0  # permacache entries live forever (until evicted)


class NamedGlobals:
    """Persistent key/value store backed by g.permacache (Redis/Memcache).

    Replaces the old Cassandra-backed implementation. Values are JSON-encoded
    so they survive serialisation round-trips identically to the original.
    """

    @classmethod
    def get(cls, key, default=NoDefault):
        from r2.lib.app_globals import g
        raw = g.permacache.get(_PREFIX + key)
        if raw is None:
            if default is NoDefault:
                raise KeyError(key)
            return default
        return json.loads(raw)

    @classmethod
    def set(cls, key, data):
        from r2.lib.app_globals import g
        g.permacache.set(_PREFIX + key, json.dumps(data))
