"""
Async SQLAlchemy engine and session factory.

Replaces the old `dbm` (DatabaseManager) multi-engine sharding layer.
All application code should use get_db() as a FastAPI dependency, or
AsyncSessionLocal() as a context manager in background tasks.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


_engine = None
_AsyncSessionLocal = None


def init_engine(db_url: str, **kwargs):
    """Initialize the engine. Called once from environment.py at startup."""
    global _engine, _AsyncSessionLocal

    defaults = dict(
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )
    defaults.update(kwargs)

    _engine = create_async_engine(db_url, **defaults)
    _AsyncSessionLocal = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def get_engine():
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _engine


def AsyncSessionLocal() -> AsyncSession:
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return _AsyncSessionLocal()


async def get_db():
    """FastAPI dependency that yields an AsyncSession per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
