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
"""Delayed execution stubs — Cassandra backend removed.

TryLater and TryLaterBySubject previously stored scheduled jobs in Cassandra.
The Cassandra backend has been removed. These classes are retained for API
compatibility but their operations are currently no-ops.

A future task can back them with a PostgreSQL ``scheduled_jobs`` table or a
dedicated task queue (e.g. Celery / RQ).
"""

import logging

from datetime import timedelta

log = logging.getLogger(__name__)


class TryLater:
    @classmethod
    def process_ready_items(cls, rowkey, ready_fn):
        log.debug('TryLater.process_ready_items: no-op (Cassandra removed)')

    @classmethod
    def run(cls):
        log.debug('TryLater.run: no-op (Cassandra removed)')

    @classmethod
    def schedule(cls, system, data, delay=None):
        log.debug('TryLater.schedule: no-op (Cassandra removed)')

    @classmethod
    def unschedule(cls, rowkey, column_keys):
        log.debug('TryLater.unschedule: no-op (Cassandra removed)')

    @classmethod
    def search(cls, rowkey, when):
        log.debug('TryLater.search: no-op (Cassandra removed)')
        return []

    @classmethod
    def cleanup(cls, rowkey, ready_items, ready_timestamps, unripe_timestamps):
        log.debug('TryLater.cleanup: no-op (Cassandra removed)')


class TryLaterBySubject:
    @classmethod
    def schedule(cls, system, subject, data, delay, trylater_rowkey=None):
        log.debug(
            'TryLaterBySubject.schedule: no-op (Cassandra removed); '
            'system=%r subject=%r delay=%r', system, subject, delay)

    @classmethod
    def search(cls, rowkey, subjects=None):
        log.debug('TryLaterBySubject.search: no-op (Cassandra removed)')
        return {}

    @classmethod
    def unschedule(cls, rowkey, colkey, schedule_rowkey):
        log.debug(
            'TryLaterBySubject.unschedule: no-op (Cassandra removed); '
            'rowkey=%r colkey=%r', rowkey, colkey)
