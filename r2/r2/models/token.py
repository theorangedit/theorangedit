"""
Token model wrappers — replaces the old Cassandra-backed Token subclasses.

All token data lives in the `tokens` PostgreSQL table via the ORM model at
r2.models.orm.tokens.Token.  This module provides thin wrapper classes that
preserve the interface expected by the rest of the codebase while delegating
all persistence to the async SQLAlchemy session stored on the per-request
context (c.db).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select

from r2.lib.context import c
from r2.models.orm.tokens import Token as _OrmToken
from r2.services.tokens import create_token as _svc_create, get_token as _svc_get


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NotFound(Exception):
    """Raised when a token lookup returns no result."""


# ---------------------------------------------------------------------------
# Base Token wrapper
# ---------------------------------------------------------------------------

class Token:
    """
    Thin wrapper around the ORM Token row.

    Fields delegated from the ORM model:
        id           — TEXT primary key (the token string itself)
        type         — discriminator string, e.g. 'oauth2_access'
        account_id   — BIGINT FK to accounts.id (nullable)
        data         — JSONB dict of type-specific fields
        expires_at   — TIMESTAMPTZ (nullable)
    """

    # Subclasses set this to restrict lookups to a single token type.
    _token_type: str = ''

    def __init__(self, orm_token: _OrmToken) -> None:
        self._orm = orm_token

    # -- ORM field pass-throughs -----------------------------------------

    @property
    def id(self) -> str:
        return self._orm.id

    @property
    def type(self) -> str:
        return self._orm.type

    @property
    def account_id(self) -> Optional[int]:
        return self._orm.account_id

    @property
    def data(self) -> dict:
        return self._orm.data or {}

    @property
    def expires_at(self) -> Optional[datetime]:
        return self._orm.expires_at

    # -- Compatibility properties ----------------------------------------

    @property
    def user_id(self) -> Optional[int]:
        """Alias for account_id (backwards-compat)."""
        return self._orm.account_id

    @property
    def valid(self) -> bool:
        """True if the token has not yet expired."""
        if self._orm.expires_at is None:
            return True
        return self._orm.expires_at > datetime.utcnow()

    # -- Persistence ---------------------------------------------------------

    @classmethod
    async def _byID(cls, token_id: str) -> 'Token':
        """Look up a token by its id string.  Raises NotFound if missing."""
        token_type = cls._token_type or None
        orm = await _svc_get(c.db, token_id, token_type=token_type)
        if orm is None:
            raise NotFound(token_id)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        token_type: str,
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'Token':
        """Create and persist a new token row."""
        orm = await _svc_create(
            c.db,
            token_type=token_type,
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        """Flush pending changes for this token to the database."""
        await c.db.flush()

    async def consume(self) -> None:
        """Delete the token (mark it as used / revoked)."""
        await c.db.execute(delete(_OrmToken).where(_OrmToken.id == self._orm.id))

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id[:8]}... type={self.type!r}>'


# ---------------------------------------------------------------------------
# OAuth2 — Client
# ---------------------------------------------------------------------------

class OAuth2Client(Token):
    """
    Represents a registered OAuth2 application.

    type='oauth2_client'
    data keys: secret, redirect_uri, app_type
    """

    _token_type = 'oauth2_client'

    @classmethod
    async def _byID(cls, client_id: str) -> 'OAuth2Client':
        orm = await _svc_get(c.db, client_id, token_type=cls._token_type)
        if orm is None:
            raise NotFound(client_id)
        return cls(orm)

    @classmethod
    async def _by_user(cls, account_id: int) -> list['OAuth2Client']:
        """Return all OAuth2 clients registered by a given user."""
        rows = (await c.db.execute(
            select(_OrmToken)
            .where(_OrmToken.type == cls._token_type)
            .where(_OrmToken.account_id == account_id)
        )).scalars().all()
        return [cls(r) for r in rows]

    @classmethod
    async def create(
        cls,
        token_type: str = 'oauth2_client',
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'OAuth2Client':
        orm = await _svc_create(
            c.db,
            token_type='oauth2_client',
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        await c.db.flush()

    # -- Convenience properties that map into the JSONB data blob ----------

    @property
    def client_id(self) -> str:
        """The client's stable identifier (same as self.id)."""
        return self._orm.id

    @property
    def secret(self) -> Optional[str]:
        return self.data.get('secret')

    @property
    def redirect_uri(self) -> Optional[str]:
        return self.data.get('redirect_uri')

    @property
    def app_type(self) -> Optional[str]:
        return self.data.get('app_type')


# ---------------------------------------------------------------------------
# OAuth2 — Access Token
# ---------------------------------------------------------------------------

class OAuth2AccessToken(Token):
    """
    Short-lived bearer token granting API access.

    type='oauth2_access'
    data keys: scope, user_id
    """

    _token_type = 'oauth2_access'

    @classmethod
    async def _byID(cls, token_id: str) -> 'OAuth2AccessToken':
        orm = await _svc_get(c.db, token_id, token_type=cls._token_type)
        if orm is None:
            raise NotFound(token_id)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        token_type: str = 'oauth2_access',
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'OAuth2AccessToken':
        orm = await _svc_create(
            c.db,
            token_type='oauth2_access',
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        await c.db.flush()

    @property
    def scope(self) -> str:
        return self.data.get('scope', '')

    @property
    def user_id(self) -> Optional[int]:  # type: ignore[override]
        """Returns the user_id stored in data (OAuth2 convention)."""
        raw = self.data.get('user_id')
        if raw is not None:
            return int(raw)
        return self._orm.account_id


# ---------------------------------------------------------------------------
# OAuth2 — Refresh Token
# ---------------------------------------------------------------------------

class OAuth2RefreshToken(Token):
    """
    Long-lived token used to obtain new access tokens.

    type='oauth2_refresh'
    data keys: scope, user_id
    """

    _token_type = 'oauth2_refresh'

    @classmethod
    async def _byID(cls, token_id: str) -> 'OAuth2RefreshToken':
        orm = await _svc_get(c.db, token_id, token_type=cls._token_type)
        if orm is None:
            raise NotFound(token_id)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        token_type: str = 'oauth2_refresh',
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'OAuth2RefreshToken':
        orm = await _svc_create(
            c.db,
            token_type='oauth2_refresh',
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        await c.db.flush()

    @property
    def scope(self) -> str:
        return self.data.get('scope', '')

    @property
    def user_id(self) -> Optional[int]:  # type: ignore[override]
        raw = self.data.get('user_id')
        if raw is not None:
            return int(raw)
        return self._orm.account_id


# ---------------------------------------------------------------------------
# OAuth2 — Authorization Code
# ---------------------------------------------------------------------------

class OAuth2AuthorizationCode(Token):
    """
    Short-lived one-time code exchanged for access/refresh tokens.

    type='oauth2_code'
    data keys: scope, redirect_uri, client_id
    """

    _token_type = 'oauth2_code'

    @classmethod
    async def _byID(cls, token_id: str) -> 'OAuth2AuthorizationCode':
        orm = await _svc_get(c.db, token_id, token_type=cls._token_type)
        if orm is None:
            raise NotFound(token_id)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        token_type: str = 'oauth2_code',
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'OAuth2AuthorizationCode':
        orm = await _svc_create(
            c.db,
            token_type='oauth2_code',
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        await c.db.flush()

    @property
    def scope(self) -> str:
        return self.data.get('scope', '')

    @property
    def redirect_uri(self) -> Optional[str]:
        return self.data.get('redirect_uri')

    @property
    def client_id(self) -> Optional[str]:
        return self.data.get('client_id')


# ---------------------------------------------------------------------------
# Password reset / email verification tokens
# ---------------------------------------------------------------------------

class PasswordResetToken(Token):
    """
    Single-use token emailed to a user to reset their password.

    type='password_reset'
    """

    _token_type = 'password_reset'

    @classmethod
    async def _byID(cls, token_id: str) -> 'PasswordResetToken':
        orm = await _svc_get(c.db, token_id, token_type=cls._token_type)
        if orm is None:
            raise NotFound(token_id)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        token_type: str = 'password_reset',
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'PasswordResetToken':
        orm = await _svc_create(
            c.db,
            token_type='password_reset',
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        await c.db.flush()


class EmailVerificationToken(Token):
    """
    Single-use token sent to verify an email address.

    type='email_verify'
    data keys: email (the address being verified)
    """

    _token_type = 'email_verify'

    @classmethod
    async def _byID(cls, token_id: str) -> 'EmailVerificationToken':
        orm = await _svc_get(c.db, token_id, token_type=cls._token_type)
        if orm is None:
            raise NotFound(token_id)
        return cls(orm)

    @classmethod
    async def create(
        cls,
        token_type: str = 'email_verify',
        account_id: Optional[int] = None,
        data: Optional[dict] = None,
        ttl_seconds: Optional[int] = None,
    ) -> 'EmailVerificationToken':
        orm = await _svc_create(
            c.db,
            token_type='email_verify',
            account_id=account_id,
            data=data,
            ttl_seconds=ttl_seconds,
        )
        return cls(orm)

    async def _commit(self) -> None:
        await c.db.flush()

    @property
    def email(self) -> Optional[str]:
        return self.data.get('email')
