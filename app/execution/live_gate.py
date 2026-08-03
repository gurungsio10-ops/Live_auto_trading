"""Phase 14 — live trading gating checklist (all 9 conditions required)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.models.domain.enums import RiskReasonCode


@dataclass(frozen=True)
class LiveGateResult:
    allowed: bool
    failed_conditions: list[str]
    reason_code: RiskReasonCode | None = None
    details: dict[str, Any] | None = None


LIVE_CONDITIONS = (
    "trading_mode_live",
    "live_trading_enabled",
    "kill_switch_off",
    "valid_credentials",
    "risk_engine_healthy",
    "market_data_healthy",
    "database_healthy",
    "reconciliation_healthy",
    "valid_live_approval_token",
)


@dataclass
class LiveReadinessState:
    risk_engine_healthy: bool = True
    market_data_healthy: bool = True
    database_healthy: bool = True
    reconciliation_healthy: bool = True
    live_approval_valid: bool = False
    clock_synced: bool = True
    account_readable: bool = True
    balances_verified: bool = True


class LiveTradingGate:
    """
    Hard gate for live order submission.
    No shortcut may activate live trading with fewer than all 9 conditions.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        state: LiveReadinessState | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.state = state or LiveReadinessState()

    def has_configured_approval_token(self) -> bool:
        token = self.settings.live_approval_token
        if token is None:
            return False
        return bool(token.get_secret_value().strip())

    def validate_approval_token(self, presented: str) -> bool:
        """Constant-time compare of a presented token against Settings."""
        token = self.settings.live_approval_token
        if token is None or not presented:
            return False
        expected = token.get_secret_value()
        if not expected.strip():
            return False
        return secrets.compare_digest(presented, expected)

    def evaluate(self) -> LiveGateResult:
        checks = {
            "trading_mode_live": self.settings.trading_mode == "live",
            "live_trading_enabled": self.settings.live_trading_enabled is True,
            "kill_switch_off": self.settings.kill_switch_enabled is False,
            "valid_credentials": self.settings.has_exchange_credentials,
            "risk_engine_healthy": self.state.risk_engine_healthy,
            "market_data_healthy": self.state.market_data_healthy,
            "database_healthy": self.state.database_healthy,
            "reconciliation_healthy": self.state.reconciliation_healthy,
            "valid_live_approval_token": (
                self.state.live_approval_valid and self.has_configured_approval_token()
            ),
        }
        assert set(checks) == set(LIVE_CONDITIONS)
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            reason = _reason_for(failed[0])
            return LiveGateResult(
                allowed=False,
                failed_conditions=failed,
                reason_code=reason,
                details=checks,
            )
        return LiveGateResult(allowed=True, failed_conditions=[], details=checks)


def _reason_for(condition: str) -> RiskReasonCode:
    return {
        "trading_mode_live": RiskReasonCode.LIVE_GATING_INCOMPLETE,
        "live_trading_enabled": RiskReasonCode.LIVE_TRADING_DISABLED,
        "kill_switch_off": RiskReasonCode.KILL_SWITCH_ACTIVE,
        "valid_credentials": RiskReasonCode.INVALID_CREDENTIALS,
        "risk_engine_healthy": RiskReasonCode.RISK_ENGINE_UNHEALTHY,
        "market_data_healthy": RiskReasonCode.MARKET_DATA_UNHEALTHY,
        "database_healthy": RiskReasonCode.DATABASE_UNHEALTHY,
        "reconciliation_healthy": RiskReasonCode.RECONCILIATION_UNHEALTHY,
        "valid_live_approval_token": RiskReasonCode.INVALID_LIVE_APPROVAL,
    }[condition]
