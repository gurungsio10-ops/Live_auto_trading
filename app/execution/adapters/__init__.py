"""Exchange adapter boundary — secrets stay server-side; live disabled by default."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.time import utc_now
from app.services.paper_session import get_paper_session


class ExchangeAdapter(ABC):
    name: str

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_balances(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_open_orders(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_exchange_status(self) -> dict[str, Any]:
        raise NotImplementedError


class MockExchangeAdapter(ExchangeAdapter):
    """Paper-mode adapter wrapping the in-process PaperSession."""

    name = "mock_exchange"

    async def test_connection(self) -> dict[str, Any]:
        return {
            "ok": True,
            "adapter": self.name,
            "mode": "paper",
            "timestamp": utc_now().isoformat(),
        }

    async def get_balances(self) -> dict[str, Any]:
        summary = get_paper_session().portfolio_summary()
        return {
            "cash_balance": summary.get("cash_balance"),
            "equity": summary.get("equity"),
            "currency": "USDT",
        }

    async def get_open_orders(self) -> list[dict[str, Any]]:
        session = get_paper_session()
        open_statuses = {"CREATED", "SUBMITTED", "PARTIALLY_FILLED", "APPROVED", "RISK_PENDING"}
        rows = []
        for order in session.order_history:
            status = getattr(order.status, "value", str(order.status))
            if status in open_statuses:
                rows.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "side": getattr(order.side, "value", str(order.side)),
                        "status": status,
                    }
                )
        return rows

    async def get_positions(self) -> list[dict[str, Any]]:
        session = get_paper_session()
        return session.positions() if hasattr(session, "positions") else []

    async def place_order(self, **kwargs: Any) -> dict[str, Any]:
        # Always go through PaperSession → risk gateway; never bypass.
        session = get_paper_session()
        payload = kwargs.get("payload") or kwargs
        return await session.place_order(payload)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "cancel_not_supported_in_mock", "order_id": order_id}

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        session = get_paper_session()
        order = session.paper.state.orders.get(order_id)
        if order is None:
            return {"ok": False, "error": "not_found", "order_id": order_id}
        return {
            "ok": True,
            "id": order.id,
            "status": getattr(order.status, "value", str(order.status)),
        }

    async def get_exchange_status(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "mode": "paper",
            "connected": True,
            "live_trading": False,
            "label": "Paper mock exchange",
            "timestamp": utc_now().isoformat(),
        }


def get_exchange_adapter() -> ExchangeAdapter:
    return MockExchangeAdapter()
