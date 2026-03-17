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
query_cache.py — compatibility shim replacing the Cassandra-backed listing cache.

CachedQuery and UserQueryCache now delegate to the Redis sorted-set listing
cache at r2.lib.db.query_cache.  CachedQueryMutator is a no-op context manager
(mutations now happen via the service layer directly).
"""

from __future__ import annotations

import asyncio
from typing import Optional


# ── Exceptions ────────────────────────────────────────────────────────────────

class NotFound(Exception):
    pass


# ── CachedQuery ───────────────────────────────────────────────────────────────

class CachedQuery:
    """Async listing query backed by Redis sorted sets."""

    def __init__(self, key: str, limit: int = 25, start: int = 0):
        self.key = key
        self.limit = limit
        self.start = start
        self._data: Optional[list] = None

    async def fetch(self) -> list[str]:
        from r2.lib.db.query_cache import get_listing
        result = await get_listing(self.key, self.start, self.limit)
        self._data = result or []
        return self._data

    @classmethod
    async def _fetch_multi(cls, queries: list['CachedQuery']) -> None:
        await asyncio.gather(*(q.fetch() for q in queries))

    def update(self, *args, **kwargs):
        pass


# ── MergedCachedQuery ─────────────────────────────────────────────────────────

class MergedCachedQuery:
    def __init__(self, queries: list[CachedQuery]):
        self.queries = queries

    async def fetch(self) -> list[str]:
        results = await asyncio.gather(*(q.fetch() for q in self.queries))
        seen = set()
        merged = []
        for batch in results:
            for item in batch:
                if item not in seen:
                    seen.add(item)
                    merged.append(item)
        return merged

    def update(self, *args, **kwargs):
        pass


# ── CachedQueryMutator ────────────────────────────────────────────────────────

class CachedQueryMutator:
    """No-op context manager — mutations flow through the service layer."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def insert(self, query, items, **kwargs):
        pass

    def delete(self, query, items, **kwargs):
        pass


# ── UserQueryCache / SubredditQueryCache ──────────────────────────────────────

class UserQueryCache:
    @classmethod
    def get(cls, key: str, limit: int = 25) -> Optional[CachedQuery]:
        return CachedQuery(key, limit=limit)

    @classmethod
    def set(cls, key: str, items: list, **kwargs) -> None:
        pass


class SubredditQueryCache(UserQueryCache):
    pass


# ── cached_query decorator ────────────────────────────────────────────────────

def cached_query(cache_class=UserQueryCache, *filter_fns):
    """No-op marker decorator."""
    def decorator(fn):
        return fn
    return decorator


# ── add_queries helper ────────────────────────────────────────────────────────

async def add_queries(queries, insert_items=None, delete_items=None, **kwargs):
    """No-op shim — listings maintained via service layer + Redis."""
    pass


# ── FakeQuery ─────────────────────────────────────────────────────────────────

class FakeQuery:
    def __init__(self, *args, **kwargs):
        pass

    async def fetch(self) -> list:
        return []

    def update(self, *args, **kwargs):
        pass
