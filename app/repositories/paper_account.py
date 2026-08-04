"""Paper account repository — dual-writes with system_state checkpoint."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import paper_persistence as store

DEFAULT_ACCOUNT_ID = "paper-default"


class PaperAccountRepository:
    def __init__(
        self, session: AsyncSession, *, account_id: str = DEFAULT_ACCOUNT_ID
    ) -> None:
        self.session = session
        self.account_id = account_id

    async def get(self) -> dict[str, Any] | None:
        return await store.load_paper_account(self.session, account_id=self.account_id)

    async def upsert(
        self,
        *,
        cash: Decimal,
        realized_pnl: Decimal,
        peak_equity: Decimal,
        daily_start_equity: Decimal,
        consecutive_losses: int,
        fees_paid: Decimal,
        reserved_capital: Decimal = Decimal("0"),
        idempotency_index: dict[str, str] | None = None,
    ) -> None:
        await store.save_paper_account(
            self.session,
            account_id=self.account_id,
            cash=cash,
            realized_pnl=realized_pnl,
            peak_equity=peak_equity,
            daily_start_equity=daily_start_equity,
            consecutive_losses=consecutive_losses,
            fees_paid=fees_paid,
            reserved_capital=reserved_capital,
            idempotency_index=idempotency_index or {},
        )
