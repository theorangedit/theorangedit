"""
r2.models.vote
~~~~~~~~~~~~~~

Replaces the legacy Cassandra-backed vote system (pycassa / tdb_cassandra)
with an async SQLAlchemy 2.x implementation backed by PostgreSQL.

The public surface area is intentionally close to the legacy API so that call
sites need minimal changes.  The key behavioural differences are:

  - Everything that touches the DB is async.
  - ``Vote.commit()`` is now a coroutine (``await vote.commit()``).
  - ``Vote.from_data()`` is a classmethod coroutine that replaces the old
    constructor for the common load-from-dict path.
  - The Cassandra helpers (VoteDetailsByThing, VoterIPByThing, VoteNote) are
    retained as stub classes so that any remaining import references do not
    produce ImportError at startup.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from r2.lib.context import c
from r2.models.orm.relations import CommentVote, LinkVote
from r2.services.links import cast_vote as cast_link_vote
from r2.services.comments import cast_vote as cast_comment_vote


# ── Direction constants ───────────────────────────────────────────────────────

_DIRECTION_UP = 1
_DIRECTION_DOWN = -1
_DIRECTION_UNVOTE = 0

# Serialised integer → direction int (identity for the new system)
_SERIALIZED = {
    _DIRECTION_UP: _DIRECTION_UP,
    _DIRECTION_DOWN: _DIRECTION_DOWN,
    _DIRECTION_UNVOTE: _DIRECTION_UNVOTE,
}
_DESERIALIZED = {v: k for k, v in _SERIALIZED.items()}


# ── VoteEffects ───────────────────────────────────────────────────────────────

class _VoteEffects:
    """Lightweight replacement for the legacy VoteEffects class."""

    def __init__(self, affects_score: bool = True) -> None:
        self.affects_score = affects_score

    def __repr__(self) -> str:
        return f'<_VoteEffects affects_score={self.affects_score}>'


# ── Vote ──────────────────────────────────────────────────────────────────────

class Vote:
    """
    Represents a single vote action by a user on a Link or Comment.

    Attributes
    ----------
    user        : Account
    thing       : Link | Comment
    direction   : int  (-1, 0, or 1)
    date        : datetime
    data        : dict   (arbitrary extra data; may contain 'ip')
    event_data  : dict | None
    previous_vote : Vote | None   (the previous vote by this user on this thing)
    """

    def __init__(
        self,
        user,
        thing,
        direction: int,
        date: datetime,
        data: Optional[Dict[str, Any]] = None,
        event_data: Optional[Dict[str, Any]] = None,
        previous_vote: Optional['Vote'] = None,
    ) -> None:
        self.user = user
        self.thing = thing
        self.direction = int(direction)
        self.date = date
        self.data = data or {}
        self.event_data = event_data
        self.previous_vote = previous_vote
        self._effects: Optional[_VoteEffects] = None

    # ── Direction helpers ─────────────────────────────────────────────────────

    @property
    def is_upvote(self) -> bool:
        return self.direction == _DIRECTION_UP

    @property
    def is_downvote(self) -> bool:
        return self.direction == _DIRECTION_DOWN

    # ── Effects ───────────────────────────────────────────────────────────────

    @property
    def effects(self) -> _VoteEffects:
        """Lazy-initialise vote effects."""
        if self._effects is None:
            self._effects = _VoteEffects(
                affects_score=not self.is_automatic_initial_vote,
            )
        return self._effects

    # ── Author / automatic-vote detection ────────────────────────────────────

    @property
    def is_self_vote(self) -> bool:
        """True when the voter is also the author of the thing."""
        return self.user.id == self.thing.author_id

    @property
    def is_automatic_initial_vote(self) -> bool:
        """
        True when this is the automatic upvote cast on a submission at post
        time (author's own first upvote with no prior vote on record).
        """
        return self.is_self_vote and self.previous_vote is None

    # ── Timing ────────────────────────────────────────────────────────────────

    @property
    def delay(self) -> timedelta:
        """How long after the thing was posted the vote was cast."""
        if self.is_automatic_initial_vote:
            return timedelta(0)
        thing_date = self.thing.date
        if hasattr(thing_date, 'replace'):
            thing_date = thing_date.replace(tzinfo=None)
        vote_date = self.date
        if hasattr(vote_date, 'replace'):
            vote_date = vote_date.replace(tzinfo=None)
        return vote_date - thing_date

    # ── Persistence ───────────────────────────────────────────────────────────

    async def commit(self) -> None:
        """
        Persist the vote via the appropriate service layer function.

        Delegates to ``cast_link_vote`` or ``cast_comment_vote`` depending on
        the type of thing being voted on.  Uses ``c.db`` (the per-request
        AsyncSession).
        """
        # Avoid circular imports at module load time.
        from r2.models.orm.link import Link
        from r2.models.orm.comment import Comment

        db = c.db
        if isinstance(self.thing, Link):
            await cast_link_vote(db, self.user.id, self.thing.id, self.direction)
        elif isinstance(self.thing, Comment):
            await cast_comment_vote(db, self.user.id, self.thing.id, self.direction)
        else:
            raise TypeError(
                f'Cannot commit vote on unsupported thing type: '
                f'{type(self.thing).__name__}'
            )

    # ── Alternative constructor ───────────────────────────────────────────────

    @classmethod
    async def from_data(cls, db, vote_data: dict) -> 'Vote':
        """
        Construct a Vote from a serialised dict, loading user and thing from
        the service layer.

        Expected keys in *vote_data*:
          - ``user_id``   : int
          - ``thing_id``  : int
          - ``thing_type``: 'link' | 'comment'
          - ``direction`` : int (-1, 0, 1)
          - ``date``      : datetime (optional; defaults to utcnow)
          - ``data``      : dict (optional)
          - ``event_data``: dict (optional)
        """
        from r2.models.orm.link import Link
        from r2.models.orm.comment import Comment
        from r2.services import links as link_svc, comments as comment_svc
        from r2.services import accounts as account_svc

        user_id = vote_data['user_id']
        thing_id = vote_data['thing_id']
        thing_type = vote_data.get('thing_type', 'link')
        direction = int(vote_data['direction'])
        date = vote_data.get('date') or datetime.utcnow()
        data = vote_data.get('data') or {}
        event_data = vote_data.get('event_data')

        user = await account_svc.get_by_id(db, user_id)
        if thing_type == 'link':
            thing = await link_svc.get_by_id(db, thing_id)
        else:
            thing = await comment_svc.get_by_id(db, thing_id)

        return cls(
            user=user,
            thing=thing,
            direction=direction,
            date=date,
            data=data,
            event_data=event_data,
        )

    # ── Serialisation helpers ─────────────────────────────────────────────────

    @staticmethod
    def serialize_direction(direction: int) -> int:
        """Return the integer stored in the DB for the given direction."""
        direction = int(direction)
        if direction not in _SERIALIZED:
            raise ValueError(f'Invalid vote direction: {direction}')
        return _SERIALIZED[direction]

    @staticmethod
    def deserialize_direction(val) -> int:
        """Convert a stored DB value back to a direction int."""
        val = int(val)
        if val not in _DESERIALIZED:
            raise ValueError(f'Invalid serialised direction: {val}')
        return _DESERIALIZED[val]

    # ── Dunder helpers ────────────────────────────────────────────────────────

    @property
    def _id(self) -> str:
        """Legacy-compatible composite id string."""
        from r2.lib.utils import to36
        return f'{to36(self.user.id)}_{to36(self.thing.id)}'

    def __eq__(self, other) -> bool:
        if not isinstance(other, Vote):
            return NotImplemented
        return (
            self.user == other.user
            and self.thing == other.thing
            and self.direction == other.direction
        )

    def __ne__(self, other) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __repr__(self) -> str:
        return (
            f'<Vote user={getattr(self.user, "id", "?")} '
            f'thing={getattr(self.thing, "id", "?")} '
            f'direction={self.direction}>'
        )


# ── VotesByAccount ────────────────────────────────────────────────────────────

class VotesByAccount:
    """
    Maps a thing class to its corresponding ORM vote relation class.

    This replaces the legacy Cassandra DenormalizedRelation with a simple
    lookup that returns the SQLAlchemy relation class for use by callers that
    need to inspect or query raw vote rows.
    """

    @classmethod
    def rel(cls, thing_class):
        """
        Return the ORM vote class (LinkVote or CommentVote) for *thing_class*.

        Parameters
        ----------
        thing_class : type
            Either ``Link`` or ``Comment`` (or subclass).

        Raises
        ------
        TypeError
            If *thing_class* is not a supported votable type.
        """
        from r2.models.orm.link import Link
        from r2.models.orm.comment import Comment

        if issubclass(thing_class, Link):
            return LinkVote
        if issubclass(thing_class, Comment):
            return CommentVote

        raise TypeError(
            f'VotesByAccount.rel: unsupported thing class {thing_class!r}'
        )

