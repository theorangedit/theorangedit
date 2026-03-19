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

_PREFIX = 'admin_notes_'


class AdminNotesBySystem:
    """Admin moderation notes backed by g.permacache.

    Notes are stored as a JSON list under ``admin_notes_{system}:{subject}``.
    Data persists as long as the cache backend is running.

    Replaces the old Cassandra-backed implementation.
    """

    @classmethod
    def _key(cls, system_name, subject):
        return f'{_PREFIX}{system_name}:{subject}'

    @classmethod
    def add(cls, system_name, subject, note, author, when=None):
        from r2.lib.app_globals import g
        key = cls._key(system_name, subject)
        notes = cls.in_display_order(system_name, subject)
        entry = {
            'note': note,
            'author': author if isinstance(author, str) else getattr(author, 'name', str(author)),
            'when': when if when is not None else time.time(),
        }
        notes.append(entry)
        g.permacache.set(key, json.dumps(notes))

    @classmethod
    def in_display_order(cls, system_name, subject):
        from r2.lib.app_globals import g
        key = cls._key(system_name, subject)
        raw = g.permacache.get(key)
        if not raw:
            return []
        try:
            notes = json.loads(raw)
        except (ValueError, TypeError):
            return []
        # newest first
        return list(reversed(notes))

    @classmethod
    def _rowkey(cls, system_name, subject):
        return f"{system_name}:{subject}"
