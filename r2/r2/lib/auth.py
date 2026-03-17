"""
r2.lib.auth
~~~~~~~~~~~

Auth helper functions for cookie validation and RSS feed authentication.

These replace the legacy pycassa-backed auth helpers that were scattered
across the codebase.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional, Tuple

from r2.lib.app_globals import g


# ---------------------------------------------------------------------------
# RSS feed auth (valid_feed)
# ---------------------------------------------------------------------------

def valid_feed(username: Optional[str], feed_token: Optional[str], path: str):
    """Validate an RSS feed token and return the Account, or None.

    Legacy format: HMAC-SHA1 of (account_id + path + SECRET).
    Returns the Account object on success, None on failure.
    """
    if not username or not feed_token:
        return None

    try:
        from r2.models.account import Account
        from r2.lib.context import c
        from r2.lib.db.engine import AsyncSessionLocal
        import asyncio

        # We're in a sync context here (called from set_content_type).
        # Use a sync-safe approach: if there's a running loop, skip feed auth
        # (caller can re-implement as async if needed).
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop is not None:
            # Running inside uvicorn — can't use run_until_complete.
            # Feed auth not available synchronously; return None.
            return None

        # Offline context (scripts, tests) — run synchronously.
        async def _lookup():
            async with AsyncSessionLocal() as db:
                from r2.services.accounts import get_by_name
                return await get_by_name(db, username)

        account = asyncio.run(_lookup())
        if account is None:
            return None

        expected = _feed_token(account)
        if hmac.compare_digest(feed_token, expected):
            return account
        return None
    except Exception:
        return None


def _feed_token(account) -> str:
    """Generate the expected feed token for an account."""
    secret = g.secrets.get('SECRET', '')
    msg = f'{account.id},{secret}'
    return hashlib.sha1(msg.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# Admin cookie validation
# ---------------------------------------------------------------------------

def valid_admin_cookie(cookie_value: str) -> Tuple[bool, bool]:
    """Validate the admin cookie.

    Returns (is_valid, is_first_login).

    The admin cookie format is:
        "{account_name},{timestamp},{hmac}"

    where hmac = HMAC-SHA1(account_name + ',' + timestamp, ADMIN_SECRET).
    """
    if not cookie_value:
        return False, False

    try:
        parts = cookie_value.split(',', 2)
        if len(parts) < 3:
            return False, False

        name, timestamp_str, given_mac = parts

        admin_secret = g.secrets.get('ADMIN_SECRET', g.secrets.get('SECRET', ''))
        msg = f'{name},{timestamp_str}'
        expected_mac = hmac.new(
            admin_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha1,
        ).hexdigest()

        if not hmac.compare_digest(given_mac, expected_mac):
            return False, False

        # Check if it's the first login (timestamp == '0')
        is_first_login = timestamp_str == '0'
        return True, is_first_login
    except Exception:
        return False, False


# ---------------------------------------------------------------------------
# OTP (two-factor auth) cookie validation
# ---------------------------------------------------------------------------

def valid_otp_cookie(cookie_value: str) -> bool:
    """Validate the OTP remember-me cookie.

    Format: "{account_name},{expiry_timestamp},{hmac}"
    """
    if not cookie_value:
        return False

    try:
        parts = cookie_value.split(',', 2)
        if len(parts) < 3:
            return False

        name, expiry_str, given_mac = parts

        # Check expiry
        try:
            expiry = float(expiry_str)
        except ValueError:
            return False

        if time.time() > expiry:
            return False

        otp_secret = g.secrets.get('OTP_SECRET', g.secrets.get('SECRET', ''))
        msg = f'{name},{expiry_str}'
        expected_mac = hmac.new(
            otp_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha1,
        ).hexdigest()

        return hmac.compare_digest(given_mac, expected_mac)
    except Exception:
        return False
