# Migration Status

Tracking the modernisation of this Reddit fork to Python 3.11 / FastAPI / SQLAlchemy 2.x async.
The original codebase used Cassandra (removed) and a custom Thing/Relation ORM (removed).

**Goal:** Delete `thing.py`, `tdb_cassandra.py`, `tdb_sql.py`, and `userrel.py` entirely.
**Status:** All four files are already deleted. ✅

---

## Completed work

### Async rewrite (Phases 1–13)
- Full FastAPI / uvicorn ASGI stack replacing Pylons/paste
- All controllers converted to `async def`
- SQLAlchemy 2.x async ORM replacing Thing/tdb_sql
- PostgreSQL as primary store; Redis for sessions/listings; Memcached for object cache
- Alembic migrations 0001–0007

### Phase A — builder.py imports ✅
`MoreChildren`, `MoreMessages`, `MoreRecursion` are plain classes defined directly
in `models/builder.py`. `CommentSavesByAccount` / `LinkSavesByAccount` removed.
No Thing/Cassandra references remain.

### Phase B — Award system ✅
`Award` and `Trophy` fully PostgreSQL-backed.
- ORM: `r2/r2/models/orm/award.py`
- Migration: `0002_create_awards_trophies.py`
- Model: `r2/r2/models/award.py` — no Thing/Relation/NotImplementedError

### Phase C — Flair user assignment ✅
`Flair` class fully rewritten, no Thing/Relation/UserRel imports remain.
- ORM: `UserFlair` table in `orm/relations.py`
- Migration: `0003_create_user_flair.py`
- Model: `r2/r2/models/flair.py`

### Phase D — Report system ✅
`Report` class fully rewritten. MultiRelation base removed.
- ORM: `LinkReport`, `CommentReport`, `SubredditReport`, `MessageReport` in `orm/relations.py`
- Migration: `0004_reports_state_and_new_tables.py`
- Model: `r2/r2/models/report.py`

### Phase E — PromoCampaign ✅
`models/promo.py` has no Thing/Relation/NotImplementedError references.
- ORM: `r2/r2/models/orm/promo.py`

### Phase F — Cassandra View stubs ✅ (mostly)
No `tdb_cassandra` imports remain in models. No `View` / `DenormalizedRelation`
subclasses with `NotImplementedError` found in `gold.py`, `ip.py`, `media_cache.py`, `rules.py`.

S1–S8 stub cleanup (all replaced with `g.permacache` implementations):

| Stub | Replacement |
|------|-------------|
| S1 — `NamedGlobals` | `g.permacache` JSON store |
| S2 — `PromoMetrics` / `LocationPromoMetrics` | `g.permacache` JSON store |
| S3 — `AdminNotesBySystem` | `g.permacache` JSON list per system:subject |
| S4 — `PerformedRulesByThing` (automoderator) | `g.permacache` with 90-day TTL |
| S5 — `TryLater` / `TryLaterBySubject` | No-op stubs (zero active callers) |
| S6 — `AccountSRFeedback` / `ExploreSettings` | `g.permacache` with per-action TTL |
| S7 — `ImagesByWikiPage` | `g.permacache` JSON dict |
| S8 — `CommentScoresByLink` | `g.permacache` JSON dict |

### Phase G — Final cleanup ✅
All four legacy db files already deleted:
- ~~`r2/r2/lib/db/thing.py`~~
- ~~`r2/r2/lib/db/tdb_cassandra.py`~~
- ~~`r2/r2/lib/db/tdb_sql.py`~~
- ~~`r2/r2/lib/db/userrel.py`~~

No remaining `from r2.lib.db import thing/tdb_cassandra/tdb_sql/userrel` outside of `lib/db/` itself.

### LabeledMulti / multireddits ✅
Full PostgreSQL implementation replacing the Cassandra stub:
- ORM: `MultiRedditORM` + `MultiRedditSubreddit` in `orm/relations.py`
- Migration: `0007_multireddits.py`
- Service: `r2/r2/services/multis.py`
- Model: `LabeledMulti` in `models/subreddit.py` — fully async, DB-backed
- Controller: `multi.py` — all endpoints async; `VMultiByPath` retired (no-op shim)
- Templates: `c.user_multis` pre-loaded in `RedditController.pre()`; `c.profile_user_multis` in `UserController.GET_listing()`
- `AccountSRPrefs.for_user` made async throughout

---

## Remaining work

None. The migration is complete.

---

## Verification

```bash
# No NotImplementedError stubs remain in models
grep -rn "raise NotImplementedError" r2/r2/models/ --include="*.py"

# No legacy db imports remain outside lib/db/
grep -rn "from r2.lib.db.thing\|from r2.lib.db import tdb_cassandra\|from r2.lib.db import tdb_sql\|from r2.lib.db import userrel" r2/r2/ --include="*.py"

# Migration chain
cd r2 && alembic history

# Tests
cd r2 && nosetests -v
```
