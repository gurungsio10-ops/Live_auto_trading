"""Risk-state repository — durable RiskEngine + session risk counters."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.paper_account import DEFAULT_ACCOUNT_ID
from app.services import paper_persistence as store


class RiskStateRepository:
    def __init__(
        self, session: AsyncSession, *, account_id: str = DEFAULT_ACCOUNT_ID
    ) -> None:
        self.session = session
        self.account_id = account_id

    async def get(self) -> dict[str, Any] | None:
        return await store.load_risk_state(self.session, account_id=self.account_id)

    async def upsert(self, payload: dict[str, Any]) -> None:
        await store.save_risk_state(self.session, account_id=self.account_id, **payload)

    async def upsert_from_session(
        self,
        *,
        circuit_breaker_open: bool,
        circuit_breaker_reason: str,
        seen_idempotency_keys: set[str] | list[str],
        reconciliation_healthy: bool,
        risk_engine_healthy: bool,
        database_healthy: bool,
        market_data_healthy: bool,
        peak_equity: Decimal,
        daily_start_equity: Decimal,
        consecutive_losses: int,
        kill_switch_enabled: bool,
        halt_reason: str = "",
    ) -> None:
        await store.save_risk_state(
            self.session,
            account_id=self.account_id,
            circuit_breaker_open=circuit_breaker_open,
            circuit_breaker_reason=circuit_breaker_reason,
            seen_idempotency_keys=list(seen_idempotency_keys),
            reconciliation_healthy=reconciliation_healthy,
            risk_engine_healthy=risk_engine_healthy,
            database_healthy=database_healthy,
            market_data_healthy=market_data_healthy,
            peak_equity=peak_equity,
            daily_start_equity=daily_start_equity,
            consecutive_losses=consecutive_losses,
            kill_switch_enabled=kill_switch_enabled,
            halt_reason=halt_reason,
        )
