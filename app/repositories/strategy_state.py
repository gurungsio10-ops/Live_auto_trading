"""Strategy selection / params repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.paper_account import DEFAULT_ACCOUNT_ID
from app.services import paper_persistence as store


class StrategyStateRepository:
    def __init__(
        self, session: AsyncSession, *, account_id: str = DEFAULT_ACCOUNT_ID
    ) -> None:
        self.session = session
        self.account_id = account_id

    async def get(self) -> dict[str, Any] | None:
        return await store.load_strategy_state(self.session, account_id=self.account_id)

    async def upsert(
        self,
        *,
        selected_strategy_id: str | None,
        running_strategies: set[str] | list[str],
        param_overrides: dict[str, dict[str, Any]],
    ) -> None:
        await store.save_strategy_state(
            self.session,
            account_id=self.account_id,
            selected_strategy_id=selected_strategy_id,
            running_strategies=list(running_strategies),
            param_overrides=param_overrides,
        )
