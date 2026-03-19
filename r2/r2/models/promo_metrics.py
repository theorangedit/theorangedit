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

_PM_PREFIX = 'promo_metrics_'
_LPM_PREFIX = 'location_promo_metrics_'


class PromoMetrics:
    """Promotion inventory metrics backed by g.permacache.

    Values are dicts mapping sr_name → int (pageview count).

    Replaces the old Cassandra-backed implementation.
    """

    @classmethod
    def get(cls, metric_name, sr_names=None):
        from r2.lib.app_globals import g
        raw = g.permacache.get(_PM_PREFIX + metric_name)
        if raw is None:
            return {}
        data = json.loads(raw)
        if sr_names is not None:
            data = {k: v for k, v in data.items() if k in sr_names}
        return data

    @classmethod
    def set(cls, metric_name, values_by_sr):
        from r2.lib.app_globals import g
        g.permacache.set(_PM_PREFIX + metric_name, json.dumps(values_by_sr))


class LocationPromoMetrics:
    """Location-level promotion inventory metrics backed by g.permacache.

    Keyed by (sr_name, location_str). The ``get`` classmethod accepts a single
    SR and a list of Location objects and returns a dict keyed by
    ``(sr, location)`` tuples — matching the calling convention in inventory.py.

    Replaces the old Cassandra-backed implementation.
    """

    @classmethod
    def _cache_key(cls, sr_name, location_str):
        return f'{_LPM_PREFIX}{sr_name}_{location_str}'

    @classmethod
    def get(cls, srs, locations):
        from r2.lib.app_globals import g
        from r2.lib.utils import tup
        srs_list = tup(srs)
        result = {}
        for sr in srs_list:
            for loc in locations:
                loc_str = str(loc) if loc is not None else ''
                raw = g.permacache.get(cls._cache_key(sr.name, loc_str))
                value = json.loads(raw) if raw is not None else 0
                result[(sr, loc)] = value
        return result

    @classmethod
    def set(cls, metrics):
        """Store a mapping of {(sr, location): value}."""
        from r2.lib.app_globals import g
        for (sr, loc), value in metrics.items():
            loc_str = str(loc) if loc is not None else ''
            g.permacache.set(cls._cache_key(sr.name, loc_str), json.dumps(value))
