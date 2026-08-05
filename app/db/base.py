"""SQLAlchemy declarative base and shared async session helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_ENGINE: AsyncEngine | None = None
_SESSION_FACTORY: async_sessionmaker[AsyncSession] | None = None


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Create a new engine (tests / one-off). Prefer ``get_shared_engine`` in app code."""
    url = database_url or get_settings().database_url
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(url, echo=False, connect_args=connect_args)


def get_shared_engine() -> AsyncEngine:
    """Process-wide shared async engine (production paper runtime)."""
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is None:
        _ENGINE = create_engine()
        _SESSION_FACTORY = async_sessionmaker(
            _ENGINE, expire_on_commit=False, class_=AsyncSession
        )
    return _ENGINE


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_shared_engine()
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Shared-session context manager for cycle/scheduler/recon paths."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_scope() as session:
        yield session


async def dispose_shared_engine() -> None:
    """Dispose the shared engine (app shutdown / test isolation)."""
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        await _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None


# Lazy aliases — avoid a second eager engine at import time.
def __getattr__(name: str) -> Any:
    if name == "engine":
        return get_shared_engine()
    if name == "SessionLocal":
        return get_session_factory()
    raise AttributeError(name)
