"""
r2.models.subreddit
~~~~~~~~~~~~~~~~~~~

Exports the Subreddit ORM model (from r2.models.orm.subreddit) augmented with
legacy Pylons/Thing-ORM compatibility shims, plus the FakeSubreddit family and
stub Cassandra classes.

Migration note:
    Old pattern                           New pattern
    ─────────────────────────────────     ──────────────────────────────────────
    Subreddit._byID(id)                   await Subreddit._byID(id)
    Subreddit._by_name(name)              await Subreddit._by_name(name)
    sr._commit()                          await sr._commit()
    sr._id / sr._fullname                 sr._id / sr._fullname  (properties)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from r2.lib.context import c
from r2.lib.utils import to36
from r2.models.orm.subreddit import Subreddit as _ORMSubreddit
from r2.models.orm.relations import (
    SubredditBanned,
    SubredditContributor,
    SubredditModerator,
    SubredditSubscriber,
)
import r2.services.subreddits as subreddits_svc


# ── Public exception ──────────────────────────────────────────────────────────

class NotFound(Exception):
    """Raised when a requested Thing does not exist."""


# ── Augmented Subreddit model ─────────────────────────────────────────────────

class Subreddit(_ORMSubreddit):
    """
    SQLAlchemy ORM model for subreddits, extended with legacy compat shims.

    All classmethods and instance methods that touch the database are async.
    They resolve the AsyncSession from ``c.db`` (the per-request ContextVar
    set by RequestContextMiddleware).
    """

    # ── Compat properties ────────────────────────────────────────────────────

    @property
    def _id(self) -> int:
        return self.id

    @property
    def _fullname(self) -> str:
        return f't5_{to36(self.id)}'

    @property
    def _id36(self) -> str:
        return to36(self.id)

    @property
    def _deleted(self) -> bool:
        return self.is_deleted

    @property
    def _spam(self) -> bool:
        return self.is_spam

    @property
    def _date(self) -> datetime:
        return self.date

    @property
    def _age(self):
        """Timedelta since creation (naive UTC)."""
        return datetime.utcnow() - self.date.replace(tzinfo=None)

    # ── Compat classmethods ───────────────────────────────────────────────────

    @classmethod
    async def _byID(
        cls,
        id_or_ids: Union[int, List[int]],
        data: bool = True,
        return_dict: bool = False,
        stale: bool = False,
    ):
        """
        Fetch one or many Subreddits by primary-key id.

        - Single int, return_dict=False → returns the Subreddit instance or
          raises NotFound.
        - Single int, return_dict=True  → returns {id: Subreddit}.
        - List of ints                  → always returns {id: Subreddit}.
        """
        db = c.db
        if isinstance(id_or_ids, (list, tuple)):
            return await subreddits_svc.get_by_ids(db, list(id_or_ids))

        sr = await subreddits_svc.get_by_id(db, id_or_ids)
        if sr is None:
            raise NotFound(f'Subreddit id={id_or_ids} not found')
        if return_dict:
            return {sr.id: sr}
        return sr

    @classmethod
    async def _by_name(
        cls,
        name: str,
        stale: bool = False,
    ) -> 'Subreddit':
        """Return Subreddit by name (case-insensitive) or raise NotFound."""
        sr = await subreddits_svc.get_by_name(c.db, name, stale=stale)
        if sr is None:
            raise NotFound(f'Subreddit name={name!r} not found')
        return sr

    @classmethod
    async def _by_names(
        cls,
        names: List[str],
    ) -> dict:
        """Bulk fetch by name. Returns {lowercase_name: Subreddit}."""
        return await subreddits_svc.get_by_names(c.db, names)

    @classmethod
    async def _by_domain(
        cls,
        domain: str,
    ) -> Optional['Subreddit']:
        """Return Subreddit mapped to a custom domain, or None."""
        return await subreddits_svc.get_by_domain(c.db, domain)

    # ── Compat instance methods ───────────────────────────────────────────────

    async def _commit(self) -> None:
        """Flush pending changes and refresh caches."""
        await c.db.flush()
        subreddits_svc._cache_invalidate(self)
        subreddits_svc._cache_set(self)

    # ── Membership helpers ────────────────────────────────────────────────────

    async def get_moderators(self) -> List[int]:
        """Return list of account_ids for this subreddit's moderators."""
        return await subreddits_svc.get_moderators(c.db, self.id)

    async def is_moderator(self, account) -> bool:
        """True if *account* is a moderator of this subreddit."""
        row = (await c.db.execute(
            select(SubredditModerator)
            .where(SubredditModerator.sr_id == self.id)
            .where(SubredditModerator.account_id == account.id)
        )).scalar_one_or_none()
        return row is not None

    async def is_subscriber(self, account) -> bool:
        """True if *account* is subscribed to this subreddit."""
        row = (await c.db.execute(
            select(SubredditSubscriber)
            .where(SubredditSubscriber.sr_id == self.id)
            .where(SubredditSubscriber.account_id == account.id)
        )).scalar_one_or_none()
        return row is not None

    async def is_contributor(self, account) -> bool:
        """True if *account* is an approved contributor."""
        row = (await c.db.execute(
            select(SubredditContributor)
            .where(SubredditContributor.sr_id == self.id)
            .where(SubredditContributor.account_id == account.id)
        )).scalar_one_or_none()
        return row is not None

    async def is_banned(self, account) -> bool:
        """True if *account* is banned from this subreddit."""
        row = (await c.db.execute(
            select(SubredditBanned)
            .where(SubredditBanned.sr_id == self.id)
            .where(SubredditBanned.account_id == account.id)
        )).scalar_one_or_none()
        return row is not None

    async def add_moderator(self, account) -> None:
        """Add *account* as a moderator (idempotent)."""
        await c.db.execute(
            pg_insert(SubredditModerator)
            .values(sr_id=self.id, account_id=account.id)
            .on_conflict_do_nothing()
        )

    async def add_subscriber(self, account) -> None:
        """Subscribe *account* to this subreddit (idempotent)."""
        await subreddits_svc.subscribe(c.db, account.id, self.id)

    async def remove_subscriber(self, account) -> None:
        """Unsubscribe *account* from this subreddit."""
        await subreddits_svc.unsubscribe(c.db, account.id, self.id)


# ── FakeSubreddit family ──────────────────────────────────────────────────────

class FakeSubreddit:
    """
    Base class for virtual subreddits that do not live in the database.

    Provides the same interface contract as Subreddit so that templates and
    controllers can treat all subreddit-like objects uniformly.
    """

    name: str = 'fake'
    title: str = ''
    type: str = 'public'
    over_18: bool = False
    lang: str = 'en'
    description: str = ''
    public_description: str = ''
    header_title: str = ''
    is_deleted: bool = False
    is_spam: bool = False

    # Fake ids — callers must not persist these.
    id: int = 0
    _id: int = 0
    _fullname: str = 't5_0'

    async def is_moderator(self, account) -> bool:
        return False

    async def is_subscriber(self, account) -> bool:
        return False

    async def is_contributor(self, account) -> bool:
        return False

    async def is_banned(self, account) -> bool:
        return False

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} name={self.name!r}>'


class DefaultSR(FakeSubreddit):
    """Represents the logged-in front page (/r/front)."""
    name = 'front'
    title = 'Front Page'


class Frontpage(DefaultSR):
    """Alias for DefaultSR — the logged-in front page."""
    name = 'front'
    title = 'Front Page'


class AllSR(FakeSubreddit):
    """Virtual subreddit that aggregates all public subreddits."""
    name = 'all'
    title = 'All'


All = AllSR()


class AllFiltered(FakeSubreddit):
    """AllSR minus user-filtered subreddits."""
    name = 'all'
    title = 'All (filtered)'


class AllMinus(FakeSubreddit):
    """AllSR minus a set of excluded subreddits."""

    def __init__(self, exclude_srs=None):
        self.exclude_srs = exclude_srs or []
        self.name = 'all'
        self.title = 'All'


class Friends(FakeSubreddit):
    """Virtual subreddit for posts by friends."""
    name = 'friends'
    title = 'Friends'


class Mod(FakeSubreddit):
    """Virtual subreddit aggregating moderated subreddits."""
    name = 'mod'
    title = 'Mod'


class ModFiltered(FakeSubreddit):
    """Mod subreddit minus user-filtered srs."""
    name = 'mod'
    title = 'Mod (filtered)'


class ModMinus(FakeSubreddit):
    """Mod minus a set of excluded subreddits."""

    def __init__(self, exclude_srs=None):
        self.exclude_srs = exclude_srs or []
        self.name = 'mod'
        self.title = 'Mod'


class Random(FakeSubreddit):
    """Sentinel for random subreddit redirect."""
    name = 'random'
    title = 'Random'


class RandomNSFW(FakeSubreddit):
    """Sentinel for random NSFW subreddit redirect."""
    name = 'randnsfw'
    title = 'Random NSFW'


class RandomSubscription(FakeSubreddit):
    """Sentinel for random subscribed subreddit redirect."""
    name = 'myrandom'
    title = 'Random Subscription'


class DomainSR(FakeSubreddit):
    """Virtual subreddit scoped to a specific link domain."""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.name = f'domain/{domain}'
        self.title = domain


class MultiReddit(FakeSubreddit):
    """Virtual subreddit that aggregates multiple subreddits."""

    def __init__(self, srs: Optional[List] = None, path: str = '') -> None:
        self.srs = srs or []
        self.path = path
        self.name = 'multi'
        self.title = 'Multi'


# ── Stub Cassandra classes ────────────────────────────────────────────────────
# These existed in the legacy Cassandra Thing ORM.  They are kept as stubs so
# that any lingering import references do not cause ImportError at startup.
# Raise NotImplementedError on any attempt to actually use them.

class _CassandraStub:
    """Base for removed Cassandra-backed relation classes."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            f'{self.__class__.__name__} is a removed Cassandra class and '
            f'cannot be instantiated.'
        )

    @classmethod
    def _byID(cls, *args, **kwargs):
        raise NotImplementedError(cls.__name__)

    @classmethod
    def _by_name(cls, *args, **kwargs):
        raise NotImplementedError(cls.__name__)


class SubscribedSubredditsByAccount(_CassandraStub):
    """Removed — was a Cassandra column-family index of subscriptions."""


class SubscriptionsByDay(_CassandraStub):
    """Removed — was a Cassandra counter for daily subscription deltas."""


class SubredditsActiveForFrontPage(_CassandraStub):
    """Removed — was a Cassandra set of front-page-eligible subreddits."""


class LabeledMulti(_CassandraStub):
    """Removed — was a Cassandra-backed user multi-reddit."""


class LabeledMultiByOwner(_CassandraStub):
    """Removed — was a Cassandra index of multis by owner account."""
