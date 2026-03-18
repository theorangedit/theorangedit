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
"""A delayed execution system — stub only, Cassandra backend removed.

TryLater and TryLaterBySubject previously stored scheduled jobs in Cassandra.
Cassandra has been removed. These stubs preserve the public API shape so
existing imports don't break, but all methods raise NotImplementedError.

To re-enable scheduled-task functionality, replace these stubs with a
PostgreSQL-backed implementation (e.g. a `scheduled_jobs` table).
"""

from datetime import timedelta

from r2.lib.app_globals import g
from r2.lib.utils import tup


_MSG = 'TryLater: Cassandra removed — re-implement with PostgreSQL scheduler'


class TryLater:
    @classmethod
    def process_ready_items(cls, rowkey, ready_fn):
        raise NotImplementedError(_MSG)

    @classmethod
    def run(cls):
        raise NotImplementedError(_MSG)

    @classmethod
    def schedule(cls, system, data, delay=None):
        raise NotImplementedError(_MSG)

    @classmethod
    def unschedule(cls, rowkey, column_keys):
        raise NotImplementedError(_MSG)

    @classmethod
    def search(cls, rowkey, when):
        raise NotImplementedError(_MSG)

    @classmethod
    def cleanup(cls, rowkey, ready_items, ready_timestamps, unripe_timestamps):
        raise NotImplementedError(_MSG)


class TryLaterBySubject:
    @classmethod
    def schedule(cls, system, subject, data, delay, trylater_rowkey=None):
        raise NotImplementedError(_MSG)

    @classmethod
    def search(cls, rowkey, subjects=None):
        raise NotImplementedError(_MSG)

    @classmethod
    def unschedule(cls, rowkey, colkey, schedule_rowkey):
        raise NotImplementedError(_MSG)
