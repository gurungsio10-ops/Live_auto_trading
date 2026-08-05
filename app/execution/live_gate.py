"""Phase 14 — live trading gating checklist (all conditions required).

Live order submission remains hard-blocked in this development phase even when
the operational checklist is complete. Use ``checklist_complete`` to inspect
readiness without enabling live execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.models.domain.enums import RiskReasonCode

LIVE_STARTUP_ACK_VALUE = "I_UNDERSTAND_LIVE_TRADING_RISKS"

LIVE_CONDITIONS = (
    "trading_mode_live",
    "live_trading_enabled",
    "live_startup_ack",
    "kill_switch_off",
    "valid_credentials",
    "risk_engine_healthy",
    "market_data_healthy",
    "database_healthy",
    "reconciliation_healthy",
    "valid_live_approval_token",
)


@dataclass(frozen=True)
class LiveGateResult:
    allowed: bool
    failed_conditions: list[str]
    reason_code: RiskReasonCode | None = None
    details: dict[str, Any] | None = None
    checklist_complete: bool = False


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

    Every checklist condition must pass for ``checklist_complete``.
    ``allowed`` is always False in this phase (live execution hard-blocked).
    """

    def __init__(
        self,
        settings: Settings | None = None,
        state: LiveReadinessState | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.state = state or LiveReadinessState()

    def evaluate(self) -> LiveGateResult:
        ack = (self.settings.live_startup_ack or "").strip()
        checks = {
            "trading_mode_live": self.settings.trading_mode == "live",
            "live_trading_enabled": self.settings.live_trading_enabled is True,
            "live_startup_ack": ack == LIVE_STARTUP_ACK_VALUE,
            "kill_switch_off": self.settings.kill_switch_enabled is False,
            "valid_credentials": self.settings.has_exchange_credentials,
            "risk_engine_healthy": self.state.risk_engine_healthy,
            "market_data_healthy": self.state.market_data_healthy,
            "database_healthy": self.state.database_healthy,
            "reconciliation_healthy": self.state.reconciliation_healthy,
            "valid_live_approval_token": self.state.live_approval_valid,
        }
        assert set(checks) == set(LIVE_CONDITIONS)
        failed = [name for name, ok in checks.items() if not ok]
        checklist_complete = len(failed) == 0
        # Hard-block: never allow live order submission from this evaluator.
        if failed:
            reason = _reason_for(failed[0])
            return LiveGateResult(
                allowed=False,
                failed_conditions=failed,
                reason_code=reason,
                details={**checks, "live_execution_hard_blocked": True},
                checklist_complete=False,
            )
        return LiveGateResult(
            allowed=False,
            failed_conditions=[],
            reason_code=RiskReasonCode.LIVE_TRADING_DISABLED,
            details={
                **checks,
                "live_execution_hard_blocked": True,
                "note": (
                    "Checklist complete but live submission is hard-disabled "
                    "in this development phase"
                ),
            },
            checklist_complete=checklist_complete,
        )


def _reason_for(condition: str) -> RiskReasonCode:
    return {
        "trading_mode_live": RiskReasonCode.LIVE_GATING_INCOMPLETE,
        "live_trading_enabled": RiskReasonCode.LIVE_TRADING_DISABLED,
        "live_startup_ack": RiskReasonCode.LIVE_GATING_INCOMPLETE,
        "kill_switch_off": RiskReasonCode.KILL_SWITCH_ACTIVE,
        "valid_credentials": RiskReasonCode.INVALID_CREDENTIALS,
        "risk_engine_healthy": RiskReasonCode.RISK_ENGINE_UNHEALTHY,
        "market_data_healthy": RiskReasonCode.MARKET_DATA_UNHEALTHY,
        "database_healthy": RiskReasonCode.DATABASE_UNHEALTHY,
        "reconciliation_healthy": RiskReasonCode.RECONCILIATION_UNHEALTHY,
        "valid_live_approval_token": RiskReasonCode.INVALID_LIVE_APPROVAL,
    }[condition]
