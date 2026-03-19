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
    MultiRedditORM,
    MultiRedditSubreddit,
    SubredditBanned,
    SubredditContributor,
    SubredditModerator,
    SubredditSubscriber,
)
import r2.services.subreddits as subreddits_svc
import r2.services.multis as multis_svc


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


# ── LabeledMulti exceptions ───────────────────────────────────────────────────

class LabeledMultiNotFound(Exception):
    pass


class TooManySubredditsError(Exception):
    pass


# ── LabeledMulti ──────────────────────────────────────────────────────────────

class LabeledMulti:
    """User multireddit — PostgreSQL-backed via multireddits + multireddit_subreddits tables."""

    MAX_SR_COUNT = 100

    def __init__(self, orm_row, srs=None, owner_account=None):
        self._orm = orm_row
        self._srs = list(srs or [])
        self._sr_props = {}
        self._owner = owner_account
        self._saved_srs = list(srs or [])

    # -- Properties -----------------------------------------------------------

    @property
    def path(self):
        return self._orm.path

    @path.setter
    def path(self, value):
        self._orm.path = value

    @property
    def name(self):
        return self._orm.name

    @name.setter
    def name(self, value):
        self._orm.name = value

    @property
    def display_name(self):
        return self._orm.display_name

    @display_name.setter
    def display_name(self, value):
        self._orm.display_name = value

    @property
    def description_md(self):
        return self._orm.description_md

    @description_md.setter
    def description_md(self, value):
        self._orm.description_md = value

    @property
    def visibility(self):
        return self._orm.visibility

    @visibility.setter
    def visibility(self, value):
        self._orm.visibility = value

    @property
    def key_color(self):
        return self._orm.key_color

    @key_color.setter
    def key_color(self, value):
        self._orm.key_color = value

    @property
    def icon_id(self):
        return self._orm.icon_id

    @icon_id.setter
    def icon_id(self, value):
        self._orm.icon_id = value

    @property
    def icon_url(self):
        return self._orm.icon_url

    @icon_url.setter
    def icon_url(self, value):
        self._orm.icon_url = value

    @property
    def weighting_scheme(self):
        return self._orm.weighting_scheme

    @weighting_scheme.setter
    def weighting_scheme(self, value):
        self._orm.weighting_scheme = value

    @property
    def kind(self):
        return self._orm.kind

    @kind.setter
    def kind(self, value):
        self._orm.kind = value

    @property
    def copied_from(self):
        return self._orm.copied_from

    @copied_from.setter
    def copied_from(self, value):
        self._orm.copied_from = value

    @property
    def srs(self):
        return self._srs

    @property
    def sr_ids(self):
        return [sr._id for sr in self._srs]

    @property
    def sr_props(self):
        return self._sr_props

    @property
    def owner(self):
        return self._owner

    # Compat: _id36 used in templates
    @property
    def _id36(self):
        return to36(self._orm.id) if self._orm.id else None

    # -- Classmethods ---------------------------------------------------------

    @classmethod
    async def _byID(cls, path: str, return_dict: bool = False):
        """Fetch a multireddit by its path string (e.g. '/user/alice/m/programming').

        Raises LabeledMultiNotFound if missing.
        """
        orm = await multis_svc.get_by_path(c.db, path)
        if orm is None:
            raise LabeledMultiNotFound(path)
        sr_rows = await multis_svc.get_sr_rows(c.db, orm.id)
        sr_id_list = [r.sr_id for r in sr_rows]
        props_map = {r.sr_id: r.sr_props for r in sr_rows}
        srs = []
        if sr_id_list:
            sr_dict = await Subreddit._byID(sr_id_list, return_dict=True)
            srs = list(sr_dict.values())
        from r2.models.account import Account
        owner = await Account._byID(orm.owner_id)
        multi = cls(orm, srs=srs, owner_account=owner)
        multi._sr_props = {sr._id: props_map.get(sr._id, {}) for sr in srs}
        if return_dict:
            return {path: multi}
        return multi

    @classmethod
    async def by_owner(cls, account, load_subreddits: bool = True):
        """Return list of LabeledMulti owned by account."""
        orm_rows = await multis_svc.get_by_owner(c.db, account._id)
        result = []
        for orm in orm_rows:
            sr_rows = await multis_svc.get_sr_rows(c.db, orm.id) if load_subreddits else []
            sr_id_list = [r.sr_id for r in sr_rows]
            props_map = {r.sr_id: r.sr_props for r in sr_rows}
            srs = []
            if sr_id_list:
                sr_dict = await Subreddit._byID(sr_id_list, return_dict=True)
                srs = list(sr_dict.values())
            multi = cls(orm, srs=srs, owner_account=account)
            multi._sr_props = {sr._id: props_map.get(sr._id, {}) for sr in srs}
            result.append(multi)
        return result

    @classmethod
    def create(cls, path: str, owner):
        """Sync factory — returns an unsaved LabeledMulti. Call await multi._commit() to persist."""
        name = path.rstrip('/').rsplit('/', 1)[-1]
        orm = MultiRedditORM(path=path, owner_id=owner._id, name=name)
        return cls(orm, owner_account=owner)

    @classmethod
    def copy(cls, path: str, source_multi, owner=None):
        """Sync factory — returns an unsaved copy of source_multi at the new path."""
        name = path.rstrip('/').rsplit('/', 1)[-1]
        src = source_multi._orm
        orm = MultiRedditORM(
            path=path,
            owner_id=(owner._id if owner else src.owner_id),
            name=name,
            display_name=src.display_name,
            description_md=src.description_md,
            visibility=src.visibility,
            key_color=src.key_color,
            icon_id=src.icon_id,
            icon_url=src.icon_url,
            weighting_scheme=src.weighting_scheme,
            kind=src.kind,
            copied_from=src.path,
        )
        effective_owner = owner or source_multi._owner
        multi = cls(orm, srs=list(source_multi._srs), owner_account=effective_owner)
        multi._sr_props = dict(source_multi._sr_props)
        return multi

    @classmethod
    def slugify(cls, owner, display_name: str) -> str:
        import re
        slug = re.sub(r'[^\w]+', '_', display_name).strip('_').lower()
        return f'/user/{owner.name}/m/{slug}'

    # -- Instance methods -----------------------------------------------------

    async def _commit(self):
        c.db.add(self._orm)
        await c.db.flush()
        await multis_svc.upsert_sr_rows(
            c.db,
            self._orm.id,
            {sr._id: self._sr_props.get(sr._id, {}) for sr in self._srs},
        )
        await c.db.flush()
        self._saved_srs = list(self._srs)

    def _revert(self):
        self._srs = list(self._saved_srs)

    async def _commit_delete(self):
        await multis_svc.delete_multi(c.db, self._orm.id)

    def add_srs(self, sr_props_dict):
        """Add subreddits. sr_props_dict: {sr_object: props_dict}."""
        existing_ids = {sr._id for sr in self._srs}
        new_srs = [sr for sr in sr_props_dict if sr._id not in existing_ids]
        if len(self._srs) + len(new_srs) > self.MAX_SR_COUNT:
            raise TooManySubredditsError(
                f'A multireddit can have at most {self.MAX_SR_COUNT} subreddits'
            )
        for sr, props in sr_props_dict.items():
            if sr._id not in existing_ids:
                self._srs.append(sr)
            self._sr_props[sr._id] = props or {}

    def clear_srs(self):
        self._srs = []
        self._sr_props = {}

    def del_srs(self, sr):
        self._srs = [s for s in self._srs if s._id != sr._id]
        self._sr_props.pop(sr._id, None)

    def set_icon_by_name(self, icon_name):
        self._orm.icon_id = icon_name

    # -- Visibility / permissions ---------------------------------------------

    def is_public(self):
        return self._orm.visibility == 'public'

    def is_hidden(self):
        return self._orm.visibility == 'hidden'

    def can_view(self, user):
        if self._orm.owner_id == getattr(user, '_id', None):
            return True
        return self.is_public()

    def can_edit(self, user):
        return self._orm.owner_id == getattr(user, '_id', None)

    def is_allowed_to_view(self, user):
        return self.can_view(user)

    def __repr__(self):
        return f'<LabeledMulti path={self._orm.path!r}>'
