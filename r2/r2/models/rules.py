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

from r2.lib.context import c
from r2.lib.i18n import _

OLD_SITEWIDE_RULES = [
    _("spam"),
    _("vote manipulation"),
    _("personal information"),
    _("sexualizing minors"),
    _("breaking reddit"),
]

SITEWIDE_RULES = [
    _("Spam"),
    _("Personal and confidential information"),
    _("Threatening, harassing, or inciting violence"),
]
MAX_RULES_PER_SUBREDDIT = 10


class SubredditRules:
    """Async wrapper for subreddit rules, backed by the subreddit_rules table."""

    @staticmethod
    def _to_dict(rule) -> dict:
        return {
            "short_name": rule.short_name,
            "description": rule.description or "",
            "priority": rule.rule_order,
            "created_utc": 0,
            "kind": rule.kind,
        }

    @classmethod
    async def create(cls, subreddit, short_name, description, kind=None, created_utc=None):
        import r2.services.rules as _svc
        return await _svc.create_rule(
            c.db, subreddit.id, short_name, description or "", kind or 'all')

    @classmethod
    async def remove_rule(cls, subreddit, short_name):
        import r2.services.rules as _svc
        await _svc.delete_rule(c.db, subreddit.id, short_name)

    @classmethod
    async def update(cls, subreddit, old_short_name, short_name, description, kind=None):
        import r2.services.rules as _svc
        return await _svc.update_rule(
            c.db, subreddit.id, old_short_name, short_name, description or "", kind or 'all')

    @classmethod
    async def reorder(cls, subreddit, short_name, priority):
        import r2.services.rules as _svc
        return await _svc.reorder_rule(c.db, subreddit.id, short_name, priority)

    @classmethod
    async def get_rule(cls, subreddit, short_name):
        import r2.services.rules as _svc
        rule = await _svc.get_rule(c.db, subreddit.id, short_name)
        return cls._to_dict(rule) if rule else None

    @classmethod
    async def get_rules(cls, subreddit, kind=None):
        import r2.services.rules as _svc
        rules = await _svc.get_rules(c.db, subreddit.id, kind)
        return [cls._to_dict(r) for r in rules]
