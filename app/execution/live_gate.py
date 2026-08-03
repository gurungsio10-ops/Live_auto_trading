"""Phase 14 — live trading gating checklist (all 9 conditions required)."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from app.core.config import Settings, get_settings
from app.models.domain.enums import RiskReasonCode
from app.reconciliation import ReconciliationService


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
    """Runtime health inputs for the 9 live conditions.

    Field wiring into the 9-condition checklist:
    - clock_synced → AND into market_data_healthy
    - account_readable → AND into valid_credentials
    - balances_verified → AND into reconciliation_healthy
      (also set by ReconciliationService after a successful compare)
    """

    risk_engine_healthy: bool = True
    market_data_healthy: bool = True
    database_healthy: bool = True
    # Fail-closed: reconciliation is unhealthy until a producer verifies.
    reconciliation_healthy: bool = False
    clock_synced: bool = True
    account_readable: bool = True
    balances_verified: bool = False


def approval_token_matches(presented: str, settings: Settings) -> bool:
    """Compare presented token to Settings.live_approval_token via hmac.compare_digest."""
    token = settings.live_approval_token
    if token is None or not presented:
        return False
    expected = token.get_secret_value()
    if not expected.strip():
        return False
    # Hash to equal-length digests so compare_digest never raises on length mismatch.
    key = b"atlas-live-approval"
    left = hmac.new(key, presented.encode("utf-8"), sha256).digest()
    right = hmac.new(key, expected.encode("utf-8"), sha256).digest()
    return hmac.compare_digest(left, right)


def build_live_gate_details(
    conditions: dict[str, bool],
) -> dict[str, Any]:
    """details always enumerates every failed condition (not just the first)."""
    failed = [name for name, ok in conditions.items() if not ok]
    return {
        "conditions": dict(conditions),
        "failed_conditions": failed,
        "failed_reason_codes": {
            name: reason_for_condition(name).value for name in failed
        },
    }


def reason_for_condition(condition: str) -> RiskReasonCode:
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


class LiveTradingGate:
    """
    Hard gate for live order submission.
    No shortcut may activate live trading with fewer than all 9 conditions.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        state: LiveReadinessState | None = None,
        *,
        presented_approval_token: str = "",
        reconciliation: ReconciliationService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.state = state or LiveReadinessState()
        self.presented_approval_token = presented_approval_token
        self.reconciliation = reconciliation

    def sync_reconciliation(self) -> None:
        """Pull fail-closed health from the reconciliation producer when attached."""
        if self.reconciliation is None:
            return
        # Ensure a comparison has been attempted at least once for status reads.
        if self.reconciliation.last_result is None:
            self.reconciliation.run()
        self.state.reconciliation_healthy = self.reconciliation.healthy
        self.state.balances_verified = self.reconciliation.balances_verified

    def has_configured_approval_token(self) -> bool:
        token = self.settings.live_approval_token
        if token is None:
            return False
        return bool(token.get_secret_value().strip())

    def validate_approval_token(self, presented: str) -> bool:
        return approval_token_matches(presented, self.settings)

    def evaluate(self) -> LiveGateResult:
        self.sync_reconciliation()
        checks = {
            "trading_mode_live": self.settings.trading_mode == "live",
            "live_trading_enabled": self.settings.live_trading_enabled is True,
            "kill_switch_off": self.settings.kill_switch_enabled is False,
            "valid_credentials": (
                self.settings.has_exchange_credentials and self.state.account_readable
            ),
            "risk_engine_healthy": self.state.risk_engine_healthy,
            "market_data_healthy": (
                self.state.market_data_healthy and self.state.clock_synced
            ),
            "database_healthy": self.state.database_healthy,
            "reconciliation_healthy": (
                self.state.reconciliation_healthy and self.state.balances_verified
            ),
            "valid_live_approval_token": self.validate_approval_token(
                self.presented_approval_token
            ),
        }
        assert set(checks) == set(LIVE_CONDITIONS)
        details = build_live_gate_details(checks)
        failed: list[str] = details["failed_conditions"]
        if failed:
            # Single top-line code; details retains every failure.
            reason = (
                RiskReasonCode.LIVE_GATING_INCOMPLETE
                if len(failed) > 1
                else reason_for_condition(failed[0])
            )
            return LiveGateResult(
                allowed=False,
                failed_conditions=list(failed),
                reason_code=reason,
                details=details,
            )
        return LiveGateResult(
            allowed=True, failed_conditions=[], reason_code=None, details=details
        )
