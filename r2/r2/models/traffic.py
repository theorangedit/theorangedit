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
These models represent the traffic statistics stored for subreddits and
promoted links.  They are written to by Pig-based MapReduce jobs and read from
various places in the UI.

All traffic statistics are divided up into three "intervals" of granularity,
hourly, daily, and monthly.  Individual hits are tracked as pageviews /
impressions, and can be safely summed.  Unique hits are tracked as well, but
cannot be summed safely because there's no way to know overlap at this point in
the data pipeline.

"""

import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import Column
from sqlalchemy.sql.expression import desc, distinct
from sqlalchemy.sql.functions import sum as sa_sum
from sqlalchemy.types import TypeDecorator

from r2.lib.memoize import memoize
from r2.lib.utils import timedelta_by_name, tup
from r2.models.link import Link
from r2.models.orm.base import Base


def memoize_traffic(**memoize_kwargs):
    """Wrap the memoize decorator and automatically determine memoize key.

    The memoize key is based off the full name (including class name) of the
    method being memoized.

    """
    def memoize_traffic_decorator(fn):
        def memoize_traffic_wrapper(cls, *args, **kwargs):
            method = ".".join((cls.__name__, fn.__name__))
            actual_memoize_decorator = memoize(method, **memoize_kwargs)
            actual_memoize_wrapper = actual_memoize_decorator(fn)
            return actual_memoize_wrapper(cls, *args, **kwargs)
        return memoize_traffic_wrapper
    return memoize_traffic_decorator


class PeekableIterator(object):
    """Iterator that supports peeking at the next item in the iterable."""

    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.item = None

    def peek(self):
        """Get the next item in the iterable without advancing our position."""
        if not self.item:
            try:
                self.item = next(self.iterator)
            except StopIteration:
                return None
        return self.item

    def next(self):
        """Get the next item in the iterable and advance our position."""
        item = self.peek()
        self.item = None
        return item


def zip_timeseries(*series, **kwargs):
    """Zip timeseries data while gracefully handling gaps in the data.

    Timeseries data is expected to be a sequence of two-tuples (date, values).
    Values is expected itself to be a tuple. The width of the values tuples
    should be the same across all elements in a timeseries sequence. The result
    will be a single sequence in timeseries format.

    Gaps in sequences are filled with an appropriate number of zeros based on
    the size of the first value-tuple of that sequence.

    """

    next_slice = (max if kwargs.get("order", "descending") == "descending"
                  else min)
    iterators = [PeekableIterator(s) for s in series]
    widths = []
    for w in iterators:
        r = w.peek()
        if r:
            date, values = r
            widths.append(len(values))
        else:
            widths.append(0)

    while True:
        items = [it.peek() for it in iterators]
        if not any(items):
            return

        current_slice = next_slice(item[0] for item in items if item)

        data = []
        for i, item in enumerate(items):
            # each item is (date, data)
            if item and item[0] == current_slice:
                data.extend(item[1])
                next(iterators[i])
            else:
                data.extend([0] * widths[i])

        yield current_slice, tuple(data)


def decrement_month(date):
    """Given a truncated datetime, return a new one one month in the past."""

    if date.day != 1:
        raise ValueError("Input must be truncated to the 1st of the month.")

    date -= datetime.timedelta(days=1)
    return date.replace(day=1)


def fill_gaps_generator(time_points, query, *columns):
    """Generate a timeseries sequence with a value for every sample expected.

    Iterate over specified time points and pull the columns listed out of
    query. If the query doesn't have data for a time point, fill the gap with
    an appropriate number of zeroes.

    """

    iterator = PeekableIterator(query)
    for t in time_points:
        row = iterator.peek()

        if row and row.date == t:
            yield t, tuple(getattr(row, c) for c in columns)
            next(iterator)
        else:
            yield t, tuple(0 for c in columns)


def fill_gaps(*args, **kwargs):
    """Listify the generator returned by fill_gaps_generator for `memoize`."""
    generator = fill_gaps_generator(*args, **kwargs)
    return list(generator)


time_range_by_interval = dict(hour=datetime.timedelta(days=4),
                              day=datetime.timedelta(weeks=8),
                              month=datetime.timedelta(weeks=52))


def get_time_points(interval, start_time=None, stop_time=None):
    """Return time points for given interval type.

    Time points are in reverse chronological order to match the sort of
    queries this will be used with. If start_time and stop_time are not
    specified they will be picked based on the interval.

    """

    def truncate_datetime(dt):
        dt = dt.replace(minute=0, second=0, microsecond=0)
        if interval in ("day", "month"):
            dt = dt.replace(hour=0)
        if interval == "month":
            dt = dt.replace(day=1)
        return dt

    if start_time and stop_time:
        start_time, stop_time = sorted([start_time, stop_time])
        # truncate stop_time to an actual traffic time point
        stop_time = truncate_datetime(stop_time)
    else:
        # the stop time is the most recent slice-time; get this by truncating
        # the appropriate amount from the current time
        stop_time = datetime.datetime.utcnow()
        stop_time = truncate_datetime(stop_time)

        # then the start time is easy to work out
        range = time_range_by_interval[interval]
        start_time = stop_time - range

    step = timedelta_by_name(interval)
    current_time = stop_time
    time_points = []

    while current_time >= start_time:
        time_points.append(current_time)
        if interval != 'month':
            current_time -= step
        else:
            current_time = decrement_month(current_time)
    return time_points


def points_for_interval(interval):
    """Calculate the number of data points to render for a given interval."""
    range = time_range_by_interval[interval]
    interval = timedelta_by_name(interval)
    return range.total_seconds() / interval.total_seconds()


async def make_history_query(db: AsyncSession, cls, interval):
    """Build a generic query showing the history of a given aggregate."""

    time_points = get_time_points(interval)
    stmt = (select(cls)
            .where(cls.date.in_(time_points)))

    # subscription stats doesn't have an interval (it's only daily)
    if hasattr(cls, "interval"):
        stmt = stmt.where(cls.interval == interval)

    stmt = stmt.order_by(desc(cls.date))

    rows = (await db.execute(stmt)).scalars().all()
    return time_points, rows


async def top_last_month(db: AsyncSession, cls, key, ids=None, num=None):
    """Aggregate a listing of the top items (by pageviews) last month.

    We use the last month because it's guaranteed to be fully computed and
    therefore will be more meaningful.

    """

    cur_month = datetime.date.today().replace(day=1)
    last_month = decrement_month(cur_month)

    stmt = (select(cls)
            .where(cls.date == last_month)
            .where(cls.interval == "month")
            .order_by(desc(cls.date), desc(cls.pageview_count)))

    if ids:
        stmt = stmt.where(getattr(cls, key).in_(ids))
    else:
        num = num or 55
        stmt = stmt.limit(num)

    rows = (await db.execute(stmt)).scalars().all()
    return [(getattr(r, key), (r.unique_count, r.pageview_count))
            for r in rows]


class CoerceToLong(TypeDecorator):
    # source:
    # https://groups.google.com/forum/?fromgroups=#!topic/sqlalchemy/3fipkThttQA

    impl = BigInteger

    def process_result_value(self, value, dialect):
        if value is not None:
            value = int(value)
        return value


def sum(column):
    """Wrapper around sqlalchemy.sql.functions.sum to handle BigInteger.

    sqlalchemy returns a Decimal for sum over BigInteger values. Detect the
    column type and coerce to long if it's a BigInteger.

    """

    if isinstance(column.property.columns[0].type, BigInteger):
        return sa_sum(column, type_=CoerceToLong)
    else:
        return sa_sum(column)


async def totals(db: AsyncSession, cls, interval):
    """Aggregate sitewide totals for self-serve promotion traffic.

    We only aggregate codenames that start with a link type prefix which
    effectively filters out all DART / 300x100 etc. traffic numbers.

    """

    time_points = get_time_points(interval)

    stmt = (select(cls.date, sum(cls.pageview_count).label("sum"))
            .where(cls.interval == interval)
            .where(cls.date.in_(time_points))
            .where(cls.codename.startswith(Link._type_prefix))
            .group_by(cls.date)
            .order_by(desc(cls.date)))
    rows = (await db.execute(stmt)).all()
    return fill_gaps(time_points, rows, "sum")


async def total_by_codename(db: AsyncSession, cls, codenames):
    """Return total lifetime pageviews (or clicks) for given codename(s)."""
    codenames = tup(codenames)
    # uses hour totals to get the most up-to-date count
    stmt = (select(cls.codename, sum(cls.pageview_count))
            .where(cls.interval == "hour")
            .where(cls.codename.in_(codenames))
            .group_by(cls.codename))
    return list((await db.execute(stmt)).all())


async def promotion_history(db: AsyncSession, cls, count_column, codename, start, stop):
    """Get hourly traffic for a self-serve promotion.

    Traffic stats are summed over all targets for classes that include a target.

    count_column should be cls.pageview_count or cls.unique_count.

    NOTE: when retrieving uniques the counts for ALL targets are summed, which
    isn't strictly correct but is the best we can do for now.

    """

    time_points = get_time_points('hour', start, stop)
    stmt = (select(cls.date, sum(count_column))
            .where(cls.interval == "hour")
            .where(cls.codename == codename)
            .where(cls.date.in_(time_points))
            .group_by(cls.date)
            .order_by(cls.date))
    rows = (await db.execute(stmt)).all()
    return [(r[0], (r[1],)) for r in rows]


async def campaign_history(db: AsyncSession, cls, codenames, start, stop):
    """Get hourly traffic for given campaigns."""
    time_points = get_time_points('hour', start, stop)
    stmt = (select(cls)
            .where(cls.interval == "hour")
            .where(cls.codename.in_(codenames))
            .where(cls.date.in_(time_points))
            .order_by(cls.date))
    rows = (await db.execute(stmt)).scalars().all()
    return [(r.date, r.codename, r.subreddit, (r.unique_count,
                                               r.pageview_count))
            for r in rows]


@memoize("traffic_last_modified", time=60 * 10)
async def get_traffic_last_modified(db: AsyncSession):
    """Guess how far behind the traffic processing system is."""
    stmt = (select(SitewidePageviews.date)
            .order_by(desc(SitewidePageviews.date))
            .limit(1))
    row = (await db.execute(stmt)).scalar_one_or_none()
    return row if row is not None else datetime.datetime.min


@memoize("missing_traffic", time=60 * 10)
async def get_missing_traffic(db: AsyncSession, start, end):
    """Check for missing hourly traffic between start and end."""

    # NOTE: start, end must be UTC time without tzinfo
    time_points = get_time_points('hour', start, end)
    stmt = (select(SitewidePageviews.date)
            .where(SitewidePageviews.interval == "hour")
            .where(SitewidePageviews.date.in_(time_points)))
    found = [t for (t,) in (await db.execute(stmt)).all()]
    return [t for t in time_points if t not in found]


class SitewidePageviews(Base):
    """Pageviews across all areas of the site."""

    __tablename__ = "traffic_aggregate"

    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", BigInteger())

    @classmethod
    @memoize_traffic(time=3600)
    async def history(cls, db: AsyncSession, interval):
        time_points, rows = await make_history_query(db, cls, interval)
        return fill_gaps(time_points, rows, "unique_count", "pageview_count")


class PageviewsBySubreddit(Base):
    """Pageviews within a subreddit (i.e. /r/something/...)."""

    __tablename__ = "traffic_subreddits"

    subreddit = Column(String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", Integer())

    @classmethod
    @memoize_traffic(time=3600)
    async def history(cls, db: AsyncSession, interval, subreddit):
        time_points, rows = await make_history_query(db, cls, interval)
        rows = [r for r in rows if r.subreddit == subreddit]
        return fill_gaps(time_points, rows, "unique_count", "pageview_count")

    @classmethod
    @memoize_traffic(time=3600 * 6)
    async def top_last_month(cls, db: AsyncSession, num=None):
        return await top_last_month(db, cls, "subreddit", num=num)

    @classmethod
    @memoize_traffic(time=3600 * 6)
    async def last_month(cls, db: AsyncSession, srs):
        ids = [sr.name for sr in srs]
        return await top_last_month(db, cls, "subreddit", ids=ids)


class PageviewsBySubredditAndPath(Base):
    """Pageviews within a subreddit with action included.

    `srpath` is the subreddit name, a dash, then the controller method called
    to render the page the user viewed. e.g. reddit.com-GET_listing. This is
    useful to determine how many pageviews in a subreddit are on listing pages,
    comment pages, or elsewhere.

    """

    __tablename__ = "traffic_srpaths"

    srpath = Column(String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", Integer())


class PageviewsByLanguage(Base):
    """Sitewide pageviews correlated by user's interface language."""

    __tablename__ = "traffic_lang"

    lang = Column(String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", BigInteger())

    @classmethod
    @memoize_traffic(time=3600)
    async def history(cls, db: AsyncSession, interval, lang):
        time_points, rows = await make_history_query(db, cls, interval)
        rows = [r for r in rows if r.lang == lang]
        return fill_gaps(time_points, rows, "unique_count", "pageview_count")

    @classmethod
    @memoize_traffic(time=3600 * 6)
    async def top_last_month(cls, db: AsyncSession):
        return await top_last_month(db, cls, "lang")


class ClickthroughsByCodename(Base):
    """Clickthrough counts for ads."""

    __tablename__ = "traffic_click"

    codename = Column("fullname", String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", Integer())

    @classmethod
    @memoize_traffic(time=3600)
    async def history(cls, db: AsyncSession, interval, codename):
        time_points, rows = await make_history_query(db, cls, interval)
        rows = [r for r in rows if r.codename == codename]
        return fill_gaps(time_points, rows, "unique_count", "pageview_count")

    @classmethod
    @memoize_traffic(time=3600)
    async def promotion_history(cls, db: AsyncSession, codename, start, stop):
        return await promotion_history(db, cls, cls.unique_count, codename, start, stop)

    @classmethod
    @memoize_traffic(time=3600)
    async def historical_totals(cls, db: AsyncSession, interval):
        return await totals(db, cls, interval)

    @classmethod
    @memoize_traffic(time=3600)
    async def total_by_codename(cls, db: AsyncSession, codenames):
        return await total_by_codename(db, cls, codenames)


class TargetedClickthroughsByCodename(Base):
    """Clickthroughs for ads, correlated by ad campaign."""

    __tablename__ = "traffic_clicktarget"

    codename = Column("fullname", String(), nullable=False, primary_key=True)
    subreddit = Column(String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", Integer())

    @classmethod
    @memoize_traffic(time=3600)
    async def promotion_history(cls, db: AsyncSession, codename, start, stop):
        return await promotion_history(db, cls, cls.unique_count, codename, start, stop)

    @classmethod
    @memoize_traffic(time=3600)
    async def total_by_codename(cls, db: AsyncSession, codenames):
        return await total_by_codename(db, cls, codenames)

    @classmethod
    async def campaign_history(cls, db: AsyncSession, codenames, start, stop):
        return await campaign_history(db, cls, codenames, start, stop)


class AdImpressionsByCodename(Base):
    """Impressions for ads."""

    __tablename__ = "traffic_thing"

    codename = Column("fullname", String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", BigInteger())

    @classmethod
    @memoize_traffic(time=3600)
    async def history(cls, db: AsyncSession, interval, codename):
        time_points, rows = await make_history_query(db, cls, interval)
        rows = [r for r in rows if r.codename == codename]
        return fill_gaps(time_points, rows, "unique_count", "pageview_count")

    @classmethod
    @memoize_traffic(time=3600)
    async def promotion_history(cls, db: AsyncSession, codename, start, stop):
        return await promotion_history(db, cls, cls.pageview_count, codename, start, stop)

    @classmethod
    @memoize_traffic(time=3600)
    async def historical_totals(cls, db: AsyncSession, interval):
        return await totals(db, cls, interval)

    @classmethod
    @memoize_traffic(time=3600)
    async def top_last_month(cls, db: AsyncSession):
        return await top_last_month(db, cls, "codename")

    @classmethod
    @memoize_traffic(time=3600)
    async def recent_codenames(cls, db: AsyncSession, fullname):
        """Get a list of recent codenames used for 300x100 ads.

        The 300x100 ads get a codename that looks like "fullname_campaign".
        This function gets a list of recent campaigns.

        """
        time_points = get_time_points('day')
        stmt = (select(distinct(cls.codename).label("codename"))
                .where(cls.date.in_(time_points))
                .where(cls.codename.startswith(fullname)))
        rows = (await db.execute(stmt)).all()
        return [row.codename for row in rows]

    @classmethod
    @memoize_traffic(time=3600)
    async def total_by_codename(cls, db: AsyncSession, codename):
        return await total_by_codename(db, cls, codename)


class TargetedImpressionsByCodename(Base):
    """Impressions for ads, correlated by ad campaign."""

    __tablename__ = "traffic_thingtarget"

    codename = Column("fullname", String(), nullable=False, primary_key=True)
    subreddit = Column(String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    interval = Column(String(), nullable=False, primary_key=True)
    unique_count = Column("unique", Integer())
    pageview_count = Column("total", Integer())

    @classmethod
    @memoize_traffic(time=3600)
    async def promotion_history(cls, db: AsyncSession, codename, start, stop):
        return await promotion_history(db, cls, cls.pageview_count, codename, start, stop)

    @classmethod
    @memoize_traffic(time=3600)
    async def total_by_codename(cls, db: AsyncSession, codenames):
        return await total_by_codename(db, cls, codenames)

    @classmethod
    async def campaign_history(cls, db: AsyncSession, codenames, start, stop):
        return await campaign_history(db, cls, codenames, start, stop)


class SubscriptionsBySubreddit(Base):
    """Subscription statistics for subreddits.

    This table is different from the rest of the traffic ones.  It only
    contains data at a daily interval (hence no `interval` column) and is
    updated separately in the subscribers cron job (see
    reddit-job-subscribers).

    """

    __tablename__ = "traffic_subscriptions"

    subreddit = Column(String(), nullable=False, primary_key=True)
    date = Column(DateTime(), nullable=False, primary_key=True)
    subscriber_count = Column("unique", Integer())

    @classmethod
    @memoize_traffic(time=3600)
    async def history(cls, db: AsyncSession, interval, subreddit):
        time_points, rows = await make_history_query(db, cls, interval)
        rows = [r for r in rows if r.subreddit == subreddit]
        return fill_gaps(time_points, rows, "subscriber_count")
