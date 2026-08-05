"""Execution connector boundary — Atlas orchestrates; engines stay external."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.time import utc_now


class ExecutionConnector(ABC):
    """
    Clean boundary for an external execution engine (e.g. future Hummingbot worker).

    Implementations must communicate via REST/WebSocket/queue/subprocess —
    never by importing third-party trading-bot source into Atlas.
    """

    name: str

    @abstractmethod
    async def start(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def pause(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def resume(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_strategies(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def start_strategy(self, strategy_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def stop_strategy(self, strategy_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_orders(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def emergency_stop(self) -> dict[str, Any]:
        raise NotImplementedError


class MockExecutionConnector(ExecutionConnector):
    """Safe in-process mock used until a remote worker is configured."""

    name = "mock_execution_connector"

    def __init__(self) -> None:
        self._running = False
        self._paused = False

    async def start(self) -> dict[str, Any]:
        self._running = True
        self._paused = False
        return {"ok": True, "state": "RUNNING", "connector": self.name}

    async def stop(self) -> dict[str, Any]:
        self._running = False
        self._paused = False
        return {"ok": True, "state": "STOPPED", "connector": self.name}

    async def pause(self) -> dict[str, Any]:
        self._paused = True
        return {"ok": True, "state": "PAUSED", "connector": self.name}

    async def resume(self) -> dict[str, Any]:
        self._paused = False
        self._running = True
        return {"ok": True, "state": "RUNNING", "connector": self.name}

    async def health(self) -> dict[str, Any]:
        state = "STOPPED"
        if self._paused:
            state = "PAUSED"
        elif self._running:
            state = "RUNNING"
        return {
            "ok": True,
            "connector": self.name,
            "state": state,
            "mode": "mock",
            "timestamp": utc_now().isoformat(),
            "note": "Mock connector only — no external engine attached",
        }

    async def get_strategies(self) -> list[dict[str, Any]]:
        return []

    async def start_strategy(self, strategy_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "mock_connector_no_remote_strategies", "strategy_id": strategy_id}

    async def stop_strategy(self, strategy_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "mock_connector_no_remote_strategies", "strategy_id": strategy_id}

    async def get_orders(self) -> list[dict[str, Any]]:
        return []

    async def get_positions(self) -> list[dict[str, Any]]:
        return []

    async def emergency_stop(self) -> dict[str, Any]:
        self._running = False
        self._paused = True
        return {"ok": True, "state": "PAUSED", "action": "emergency_stop"}


_CONNECTOR: ExecutionConnector | None = None


def get_execution_connector() -> ExecutionConnector:
    global _CONNECTOR
    if _CONNECTOR is None:
        _CONNECTOR = MockExecutionConnector()
    return _CONNECTOR
