"""
Account service — replaces Account Thing ORM calls.

All functions are async and take an AsyncSession.  The memcache layer
(g.thingcache) is preserved as a thin caching wrapper matching the old
Account._cache = g.thingcache pattern.
"""

from __future__ import annotations

import hashlib
import hmac
import time as _time
from typing import Optional

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from r2.lib.app_globals import g
from r2.models.orm.account import Account, AccountKarma

COOKIE_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S'

# ── Cache helpers ────────────────────────────────────────────────────────────

def _cache_key(account_id: int) -> str:
    return f'account:{account_id}'

def _name_cache_key(name: str) -> str:
    return f'account_name:{name.lower()}'

def _cache_get(account_id: int) -> Optional[Account]:
    if g.thingcache:
        return g.thingcache.get(_cache_key(account_id))
    return None

def _cache_set(account: Account) -> None:
    if g.thingcache:
        g.thingcache.set(_cache_key(account.id), account)
        g.thingcache.set(_name_cache_key(account.name), account.id)

def _cache_invalidate(account: Account) -> None:
    if g.thingcache:
        g.thingcache.delete(_cache_key(account.id))
        g.thingcache.delete(_name_cache_key(account.name))


# ── Retrieval ────────────────────────────────────────────────────────────────

async def get_by_id(
    db: AsyncSession,
    account_id: int,
    use_cache: bool = True,
) -> Optional[Account]:
    """Return an Account by primary key, or None if not found."""
    if use_cache:
        cached = _cache_get(account_id)
        if cached is not None:
            return cached

    result = await db.get(Account, account_id)
    if result is not None:
        _cache_set(result)
    return result


async def get_by_name(
    db: AsyncSession,
    name: str,
    allow_deleted: bool = False,
) -> Optional[Account]:
    """Return an Account by username (case-insensitive), or None."""
    name_lower = name.lower()

    # Check name→id cache first
    if g.thingcache:
        cached_id = g.thingcache.get(_name_cache_key(name_lower))
        if cached_id is not None:
            return await get_by_id(db, cached_id)

    stmt = select(Account).where(func.lower(Account.name) == name_lower)
    if not allow_deleted:
        stmt = stmt.where(Account.is_deleted == False)
    stmt = stmt.limit(1)

    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is not None:
        _cache_set(row)
    return row


async def get_by_ids(
    db: AsyncSession,
    account_ids: list[int],
) -> dict[int, Account]:
    """Bulk fetch accounts by id. Returns {id: Account}."""
    if not account_ids:
        return {}

    result = {}
    missing = []
    for aid in account_ids:
        cached = _cache_get(aid)
        if cached is not None:
            result[aid] = cached
        else:
            missing.append(aid)

    if missing:
        rows = (await db.execute(
            select(Account).where(Account.id.in_(missing))
        )).scalars().all()
        for row in rows:
            _cache_set(row)
            result[row.id] = row

    return result


# ── Password / auth ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    salt = bcrypt.gensalt(rounds=getattr(g, 'bcrypt_work_factor', 12))
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Return True if password matches the stored hash.

    Handles three legacy formats:
      - bcrypt (prefix $2a$ or $2b$)
      - salted sha1 (43-char hex)
      - unsalted sha1 (40-char hex)
    """
    if hashed.startswith('$2') or hashed.startswith('$2a$') or hashed.startswith('$2b$'):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False

    # Legacy sha1 paths
    if len(hashed) == 43:
        # salted sha1: first 3 chars are salt
        salt = hashed[:3]
        expected = salt + hashlib.sha1((salt + password).encode()).hexdigest()
        return hashed == expected
    if len(hashed) == 40:
        # unsalted sha1
        return hashed == hashlib.sha1(password.encode()).hexdigest()

    return False


async def authenticate(
    db: AsyncSession,
    name: str,
    password: str,
) -> Optional[Account]:
    """Return Account if credentials are valid, else None.

    Also silently re-hashes legacy sha1 passwords to bcrypt.
    """
    account = await get_by_name(db, name)
    if account is None or account.is_deleted:
        return None

    if not verify_password(password, account.password):
        return None

    # Upgrade legacy password to bcrypt in-place
    if not account.password.startswith('$2'):
        account.password = hash_password(password)
        await db.flush()
        _cache_invalidate(account)
        _cache_set(account)

    return account


# ── Session cookies ──────────────────────────────────────────────────────────

def make_cookie(account: Account, timestr: Optional[str] = None) -> str:
    """Return the session cookie string for this account.

    Format: "{id},{timestr},{sha1(id+','+timestr+','+password+','+SECRET)}"
    Matches the legacy Account.make_cookie() format exactly.
    """
    timestr = timestr or _time.strftime(COOKIE_TIMESTAMP_FORMAT)
    id_time = f'{account.id},{timestr}'
    secret = g.secrets.get('SECRET', '')
    to_hash = ','.join((id_time, account.password, secret))
    digest = hashlib.sha1(to_hash.encode('utf-8')).hexdigest()
    return f'{id_time},{digest}'


def validate_cookie(
    account: Account,
    cookie_str: str,
) -> bool:
    """Return True if cookie_str is a valid session cookie for account."""
    try:
        _, timestr, _ = cookie_str.split(',', 2)
    except ValueError:
        return False
    expected = make_cookie(account, timestr)
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(cookie_str, expected)


# ── Registration ─────────────────────────────────────────────────────────────

async def register(
    db: AsyncSession,
    name: str,
    password: str,
    email: str = '',
    ip: str = '',
) -> Account:
    """Create and return a new Account.

    Raises ValueError if the name is already taken.
    """
    existing = await get_by_name(db, name)
    if existing is not None:
        raise ValueError(f'Account {name!r} already exists')

    account = Account(
        name=name,
        password=hash_password(password),
        email=email,
    )
    db.add(account)
    await db.flush()  # populate account.id
    _cache_set(account)
    return account


# ── Karma ────────────────────────────────────────────────────────────────────

async def get_karma(
    db: AsyncSession,
    account_id: int,
) -> list[AccountKarma]:
    """Return all AccountKarma rows for this account."""
    rows = (await db.execute(
        select(AccountKarma).where(AccountKarma.account_id == account_id)
    )).scalars().all()
    return list(rows)


async def get_total_karma(
    db: AsyncSession,
    account_id: int,
    kind: str = 'link',
) -> int:
    """Return the sum of link_karma or comment_karma across all subreddits."""
    col = AccountKarma.link_karma if kind == 'link' else AccountKarma.comment_karma
    result = await db.execute(
        select(func.coalesce(func.sum(col), 0))
        .where(AccountKarma.account_id == account_id)
    )
    return int(result.scalar())


async def increment_karma(
    db: AsyncSession,
    account_id: int,
    sr_id: int,
    link_delta: int = 0,
    comment_delta: int = 0,
) -> None:
    """Atomically increment karma for an account in a subreddit (upsert)."""
    stmt = pg_insert(AccountKarma).values(
        account_id=account_id,
        sr_id=sr_id,
        link_karma=link_delta,
        comment_karma=comment_delta,
    ).on_conflict_do_update(
        index_elements=['account_id', 'sr_id'],
        set_={
            'link_karma': AccountKarma.link_karma + link_delta,
            'comment_karma': AccountKarma.comment_karma + comment_delta,
        }
    )
    await db.execute(stmt)
    _cache_invalidate(await get_by_id(db, account_id, use_cache=False)
                      or Account(id=account_id))


# ── Updates ──────────────────────────────────────────────────────────────────

async def update_account(
    db: AsyncSession,
    account: Account,
    **kwargs,
) -> Account:
    """Update arbitrary account fields and flush to DB."""
    for key, value in kwargs.items():
        setattr(account, key, value)
    await db.flush()
    _cache_invalidate(account)
    _cache_set(account)
    return account


async def change_password(
    db: AsyncSession,
    account: Account,
    new_password: str,
) -> None:
    """Change an account's password. Invalidates all existing sessions."""
    account.password = hash_password(new_password)
    await db.flush()
    _cache_invalidate(account)
    _cache_set(account)
