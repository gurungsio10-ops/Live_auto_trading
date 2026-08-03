"""Database-backed user store with hashed passwords."""

from __future__ import annotations

import os
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.passwords import hash_password, verify_password
from app.core.time import utc_now
from app.db.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserStore:
    """Async CRUD + verification helpers over the ``users`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _ensure_table(self) -> None:
        # Resilience: create the table if migrations haven't been applied yet
        # (checkfirst makes this a no-op when it already exists).
        bind = self.session.get_bind()
        engine = getattr(bind, "engine", bind)
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: UserORM.__table__.create(sync_conn, checkfirst=True)
            )

    async def get(self, username: str) -> UserORM | None:
        try:
            result = await self.session.execute(
                select(UserORM).where(UserORM.username == username)
            )
        except OperationalError:
            await self.session.rollback()
            await self._ensure_table()
            result = await self.session.execute(
                select(UserORM).where(UserORM.username == username)
            )
        return result.scalar_one_or_none()

    async def create(self, username: str, password: str) -> UserORM:
        user = UserORM(
            id=uuid4().hex,
            username=username,
            password_hash=hash_password(password),
            created_at=utc_now(),
        )
        self.session.add(user)
        await self.session.commit()
        return user

    async def verify(self, username: str, password: str) -> bool:
        user = await self.get(username)
        if user is None:
            return False
        return verify_password(password, user.password_hash)

    async def ensure_seeded(self) -> None:
        """Seed the default dashboard admin from env if the store is empty."""
        username = os.getenv("ATLAS_DASHBOARD_USER", "admin")
        password = os.getenv("ATLAS_DASHBOARD_PASSWORD", "atlas")
        if await self.get(username) is None:
            await self.create(username, password)
