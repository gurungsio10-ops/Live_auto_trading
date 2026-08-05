"""Central safety guard — blocks live orders, futures, leverage, withdrawals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import LiveTradingDisabledError


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    allowed: bool
    reason: str
    code: str


class SafetyGuard:
    """Authoritative pre-flight checks independent of the risk engine."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def assert_paper_only(self) -> None:
        if self.settings.trading_mode != "paper":
            raise LiveTradingDisabledError(
                "Only TRADING_MODE=paper is permitted in this milestone."
            )
        if self.settings.live_trading_enabled:
            raise LiveTradingDisabledError(
                "ENABLE_LIVE_TRADING must remain false for the paper MVP."
            )
        if self.settings.runtime_mode.value == "LIVE":
            raise LiveTradingDisabledError("LIVE runtime is hard-blocked.")

    def check_order_intent(
        self,
        *,
        market_type: str = "spot",
        leverage: Decimal | int | float | str = 1,
        action: str = "order",
    ) -> SafetyDecision:
        """Return a structured allow/deny for broker-bound intents."""
        self.assert_paper_only()
        market = (market_type or "spot").lower().strip()
        if market in {"future", "futures", "swap", "perpetual", "perp"}:
            return SafetyDecision(
                False, "Futures trading is disabled in the paper MVP", "FUTURES_BLOCKED"
            )
        if action.lower().strip() in {"withdraw", "withdrawal", "transfer_out"}:
            return SafetyDecision(
                False, "Withdrawals are disabled", "WITHDRAWALS_BLOCKED"
            )
        lev = Decimal(str(leverage))
        if lev != Decimal("1"):
            return SafetyDecision(
                False,
                "Leverage must be 1x; leveraged trading is disabled",
                "LEVERAGE_BLOCKED",
            )
        return SafetyDecision(True, "paper spot order permitted", "OK")

    def public_status(self) -> dict[str, Any]:
        return {
            "trading_mode": self.settings.trading_mode,
            "runtime_mode": self.settings.runtime_mode.value,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "trading_enabled": self.settings.trading_enabled,
            "futures_allowed": False,
            "leverage_allowed": False,
            "withdrawals_allowed": False,
            "live_orders_allowed": False,
            "paper_only": True,
        }


def get_safety_guard(settings: Settings | None = None) -> SafetyGuard:
    return SafetyGuard(settings)
