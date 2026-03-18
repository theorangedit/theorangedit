import datetime

from r2.lib.app_globals import g
from r2.lib.contrib.ipaddress import ip_address


__all__ = ["IPsByAccount", "AccountsByIP"]


class IPsByAccount:
    """IP tracking by account — PostgreSQL-backed via IpTracking ORM."""

    @classmethod
    async def set(cls, account_id, ip, date=None):
        import r2.services.ip as _svc
        from r2.lib.context import c
        if ip_address(ip).is_private:
            g.stats.simple_event('ip.private_ip_storage_prevented')
            g.stats.count_string('private_ip_storage_prevented', ip)
            return
        await _svc.record(c.db, account_id=account_id, ip=ip, date=date)

    @classmethod
    async def get(cls, account_id, column_count=100, **kwargs):
        """Return [{datetime: ip}, ...] most-recent-first."""
        import r2.services.ip as _svc
        from r2.lib.context import c
        return await _svc.get_ips_for_account(c.db, account_id, column_count=column_count)


class AccountsByIP:
    """Account tracking by IP — PostgreSQL-backed via IpTracking ORM."""

    @classmethod
    async def set(cls, ip, account_id, date=None):
        import r2.services.ip as _svc
        from r2.lib.context import c
        await _svc.record(c.db, account_id=account_id, ip=ip, date=date)

    @classmethod
    async def get(cls, ip, column_count=100, **kwargs):
        """Return [{datetime: account_id}, ...] most-recent-first."""
        import r2.services.ip as _svc
        from r2.lib.context import c
        return await _svc.get_accounts_for_ip(c.db, ip, column_count=column_count)


async def set_account_ip(account_id, ip, date=None):
    """Record an IP/account association in both directions."""
    from r2.lib.context import c
    import r2.services.ip as _svc

    if ip_address(ip).is_private:
        g.stats.simple_event('ip.private_ip_storage_prevented')
        g.stats.count_string('private_ip_storage_prevented', ip)
        return

    if date is None:
        date = datetime.datetime.now(g.tz)
    await _svc.record(c.db, account_id=account_id, ip=ip, date=date)
