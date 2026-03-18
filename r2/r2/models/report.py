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
Report model — PostgreSQL-backed, fully async.

The four legacy Relation sub-classes (_LinkReport, _CommentReport,
_SubredditReport, _MessageReport) and the MultiRelation base have been
replaced by four ORM tables in r2.models.orm.relations.  All public methods
on Report are now async.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from r2.lib.context import c
from r2.lib.app_globals import g
from r2.models import Account
import r2.services.reports as _svc


class Report:
    """Async proxy for the report tables."""

    @classmethod
    async def new(cls, user, thing, reason: Optional[str] = None):
        """File a report by *user* against *thing*.

        Increments thing.reported, queues cache updates, and fires the
        new_report AMQP event.  Returns None if the report was a duplicate.
        """
        from r2.lib.db import queries

        proxy = await _svc.new_report(c.db, account_id=user._id, thing=thing, reason=reason)
        if proxy is None:
            g.log.debug("Ignoring duplicate report on %r", thing)
            return None

        # Increment reported counter on the thing
        thing.reported = getattr(thing, 'reported', 0) + 1
        await thing._commit()

        # Increment reported counter on the author if applicable
        if hasattr(thing, 'author_id'):
            author = await Account._byID(thing.author_id, data=True)
            author.reported = getattr(author, 'reported', 0) + 1
            await author._commit()

        if not getattr(thing, "ignore_reports", False):
            queries.new_report(thing, proxy)

            if thing._spam:
                await cls.accept(thing)

        return proxy

    @classmethod
    async def for_thing(cls, thing) -> list:
        """Return all report proxies for *thing*."""
        return await _svc.get_reports_for_thing(c.db, thing)

    @classmethod
    async def accept(cls, things, correct: bool = True) -> None:
        """Mark reports on *things* as accepted (correct=True) or rejected."""
        from r2.lib.utils import tup
        from r2.lib.db import queries

        things = tup(things)
        await _svc.accept_reports(c.db, things, correct=correct)

        # Flush state changes (reported=0 was set inside accept_reports)
        for thing in things:
            await thing._commit()

        queries.clear_reports(things, [])

    @classmethod
    async def get_reports(cls, wrapped, max_user_reasons: int = 20):
        """Return (mod_reports, user_reports) for a wrapped item.

        mod_reports: list of (reason, mod_name) tuples
        user_reports: list of (reason, count) tuples
        """
        if not (wrapped.reported > 0 and
                (wrapped.can_ban or
                 getattr(wrapped, "promoted", None) and c.user_is_sponsor)):
            return [], []

        reports = await cls.for_thing(wrapped.lookups[0])

        if g.automoderator_account:
            automoderator = await Account._by_name(g.automoderator_account)
        else:
            automoderator = None

        # Moderator date lookup — SubredditModerator table
        from r2.models.orm.relations import SubredditModerator
        from sqlalchemy import select
        mod_rows = await c.db.execute(
            select(SubredditModerator).where(
                SubredditModerator.sr_id == wrapped.sr_id
            )
        )
        mod_dates = {row.account_id: row.date for row in mod_rows.scalars().all()}

        mod_report_proxies = []
        user_reports = []

        for report in reports:
            if automoderator and report._thing1_id == automoderator._id:
                mod_report_proxies.append(report)
            elif (report._thing1_id in mod_dates and
                    report._date >= mod_dates[report._thing1_id]):
                mod_report_proxies.append(report)
            else:
                user_reports.append(report)

        mods = await Account._byID(
            [r._thing1_id for r in mod_report_proxies],
            data=True,
            return_dict=True,
        )
        mod_reports = [
            (report.reason, mods[report._thing1_id].name)
            for report in mod_report_proxies
        ]

        user_reports = Counter(r.reason for r in user_reports)
        user_reports = user_reports.most_common(max_user_reasons)

        return mod_reports, user_reports

    @classmethod
    def get_reasons(cls, wrapped):
        """Deprecated — returns a deprecation notice if the item has reports."""
        if wrapped.can_ban and wrapped.reported > 0:
            return [("This attribute is deprecated. Please use mod_reports "
                     "and user_reports instead.")]
        return []
