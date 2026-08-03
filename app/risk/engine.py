"""Deterministic risk engine. Every order must pass through here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any

from app.core.config import Settings, get_settings
from app.core.time import ensure_utc, utc_now
from app.models.domain.enums import OrderType, RiskDecision, RiskReasonCode
from app.models.domain.market import SymbolInfo
from app.models.domain.trading import OrderRequest, PortfolioState, RiskEvaluation


@dataclass
class RiskEngineState:
    """Mutable runtime risk state (orders, circuit breaker, health)."""

    recent_order_times: list[datetime] = field(default_factory=list)
    seen_idempotency_keys: set[str] = field(default_factory=set)
    circuit_breaker_open: bool = False
    circuit_breaker_reason: str = ""
    risk_engine_healthy: bool = True
    market_data_healthy: bool = True
    database_healthy: bool = True
    reconciliation_healthy: bool = True
    last_market_data_ts: datetime | None = None


@dataclass
class RiskContext:
    portfolio: PortfolioState
    symbol_info: SymbolInfo | None = None
    mark_price: Decimal | None = None
    market_data_ts: datetime | None = None
    trading_mode: str = "paper"
    live_trading_enabled: bool = False
    kill_switch_enabled: bool = False
    has_exchange_credentials: bool = False
    live_approval_valid: bool = False
    exchange_env: str = "paper"


class RiskEngine:
    """
    Evaluates order requests. Output: APPROVED / REJECTED / REDUCED / HALTED.
    Structurally required before any execution path.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        state: RiskEngineState | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.state = state or RiskEngineState()

    def evaluate(self, request: OrderRequest, context: RiskContext) -> RiskEvaluation:
        checks: dict[str, Any] = {}

        if not self.state.risk_engine_healthy:
            return self._halt(RiskReasonCode.RISK_ENGINE_UNHEALTHY, "Risk engine unhealthy", checks)

        if self.settings.kill_switch_enabled or context.kill_switch_enabled:
            return self._halt(RiskReasonCode.KILL_SWITCH_ACTIVE, "Kill switch active", checks)

        if self.state.circuit_breaker_open:
            return self._halt(
                RiskReasonCode.CIRCUIT_BREAKER_OPEN,
                self.state.circuit_breaker_reason or "Circuit breaker open",
                checks,
            )

        if context.trading_mode == "live" or self.settings.trading_mode == "live":
            live_eval = self._check_live_gating(context, checks)
            if live_eval is not None:
                return live_eval

        if not self.state.market_data_healthy:
            return self._reject(RiskReasonCode.MARKET_DATA_UNHEALTHY, "Market data unhealthy", checks)

        if not self.state.database_healthy:
            return self._reject(RiskReasonCode.DATABASE_UNHEALTHY, "Database unhealthy", checks)

        if not self.state.reconciliation_healthy:
            return self._reject(
                RiskReasonCode.RECONCILIATION_UNHEALTHY, "Reconciliation unhealthy", checks
            )

        # Stale data
        md_ts = context.market_data_ts or self.state.last_market_data_ts
        if md_ts is not None:
            age = utc_now() - ensure_utc(md_ts)
            stale_after = timedelta(seconds=self.settings.market_data_stale_seconds)
            checks["market_data_age_seconds"] = age.total_seconds()
            if age > stale_after:
                return self._reject(RiskReasonCode.DATA_STALE, "Market data stale", checks)

        # Duplicate idempotency
        if request.idempotency_key in self.state.seen_idempotency_keys:
            return self._reject(RiskReasonCode.DUPLICATE_ORDER, "Duplicate idempotency key", checks)

        # Price / quantity validity
        if request.quantity <= 0:
            return self._reject(RiskReasonCode.INVALID_QUANTITY, "Quantity must be > 0", checks)
        if request.order_type == OrderType.LIMIT:
            if request.price is None or request.price <= 0:
                return self._reject(RiskReasonCode.INVALID_PRICE, "Limit price required", checks)
        mark = context.mark_price
        if mark is not None and mark <= 0:
            return self._reject(RiskReasonCode.INVALID_PRICE, "Mark price invalid", checks)

        price = request.price if request.price is not None else mark
        if price is None or price <= 0:
            return self._reject(RiskReasonCode.INVALID_PRICE, "No valid price", checks)

        # Precision / min size
        qty = request.quantity
        if context.symbol_info is not None:
            info = context.symbol_info
            step = info.step_size
            if step > 0:
                quantized = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
                if quantized != qty:
                    return self._reject(
                        RiskReasonCode.PRECISION_INVALID, "Quantity precision invalid", checks
                    )
            if qty < info.min_quantity:
                return self._reject(RiskReasonCode.MIN_ORDER_SIZE, "Below min quantity", checks)
            notional = qty * price
            min_notional = max(info.min_notional, self.settings.min_order_notional)
            if notional < min_notional:
                return self._reject(RiskReasonCode.MIN_ORDER_SIZE, "Below min notional", checks)
            if info.tick_size > 0 and request.price is not None:
                ticks = request.price / info.tick_size
                if ticks != ticks.to_integral_value():
                    return self._reject(
                        RiskReasonCode.PRECISION_INVALID, "Price tick invalid", checks
                    )
        else:
            notional = qty * price
            if notional < self.settings.min_order_notional:
                return self._reject(RiskReasonCode.MIN_ORDER_SIZE, "Below min notional", checks)

        # Order frequency
        now = utc_now()
        window_start = now - timedelta(minutes=1)
        self.state.recent_order_times = [
            t for t in self.state.recent_order_times if ensure_utc(t) >= window_start
        ]
        if len(self.state.recent_order_times) >= self.settings.max_orders_per_minute:
            return self._reject(
                RiskReasonCode.MAX_ORDER_FREQUENCY, "Order frequency exceeded", checks
            )

        portfolio = context.portfolio

        # Daily loss / drawdown / consecutive losses
        if portfolio.peak_equity > 0:
            daily_loss_pct = (
                -portfolio.daily_pnl / portfolio.peak_equity
                if portfolio.daily_pnl < 0
                else Decimal("0")
            )
            checks["daily_loss_pct"] = str(daily_loss_pct)
            if daily_loss_pct >= self.settings.max_daily_loss:
                return self._reject(
                    RiskReasonCode.DAILY_LOSS_LIMIT_REACHED, "Daily loss limit", checks
                )
            if portfolio.drawdown >= self.settings.max_drawdown:
                return self._reject(
                    RiskReasonCode.MAX_DRAWDOWN_REACHED, "Max drawdown reached", checks
                )

        if portfolio.consecutive_losses >= self.settings.max_consecutive_losses:
            return self._reject(
                RiskReasonCode.MAX_CONSECUTIVE_LOSSES, "Max consecutive losses", checks
            )

        open_positions = len(portfolio.open_positions)
        checks["open_positions"] = open_positions
        reducing = request.reduce_only or any(
            p.symbol == request.symbol and p.quantity > 0 for p in portfolio.open_positions
        )
        if not reducing and open_positions >= self.settings.max_open_positions:
            return self._reject(
                RiskReasonCode.MAX_OPEN_POSITIONS, "Max open positions", checks
            )

        # Exposure checks + optional reduction
        equity = portfolio.equity if portfolio.equity > 0 else portfolio.cash_balance
        position_notional = qty * price
        position_exposure = position_notional / equity if equity > 0 else Decimal("1")
        existing_exposure = sum(
            (p.quantity * (context.mark_price or p.current_price) for p in portfolio.open_positions),
            Decimal("0"),
        ) / equity if equity > 0 else Decimal("0")
        portfolio_exposure = existing_exposure + position_exposure
        checks["position_exposure"] = str(position_exposure)
        checks["portfolio_exposure"] = str(portfolio_exposure)

        approved_qty = qty
        reason = RiskReasonCode.OK
        decision = RiskDecision.APPROVED

        # Max risk per trade (stop-based if stop present, else fixed fractional notional)
        risk_budget = equity * self.settings.max_risk_per_trade
        if request.stop_loss is not None and request.stop_loss > 0:
            per_unit_risk = abs(price - request.stop_loss)
            if per_unit_risk > 0:
                max_qty_by_risk = (risk_budget / per_unit_risk).quantize(
                    Decimal("0.00000001"), rounding=ROUND_DOWN
                )
                if max_qty_by_risk <= 0:
                    return self._reject(
                        RiskReasonCode.MAX_RISK_PER_TRADE, "Risk per trade too high", checks
                    )
                if max_qty_by_risk < approved_qty:
                    approved_qty = max_qty_by_risk
                    decision = RiskDecision.REDUCED
                    reason = RiskReasonCode.SIZE_REDUCED_BY_RISK
        else:
            max_notional = risk_budget / self.settings.max_risk_per_trade * self.settings.max_risk_per_trade
            # fixed-fractional: cap notional at max_risk_per_trade * equity / assumed 100% stop
            max_qty_ff = (risk_budget / price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            if max_qty_ff < approved_qty:
                approved_qty = max_qty_ff
                decision = RiskDecision.REDUCED
                reason = RiskReasonCode.SIZE_REDUCED_BY_RISK

        max_pos_notional = equity * self.settings.max_position_exposure
        if approved_qty * price > max_pos_notional:
            reduced = (max_pos_notional / price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            if reduced <= 0:
                return self._reject(
                    RiskReasonCode.MAX_POSITION_EXPOSURE, "Position exposure too high", checks
                )
            approved_qty = reduced
            decision = RiskDecision.REDUCED
            reason = RiskReasonCode.SIZE_REDUCED_BY_RISK

        max_port_notional = equity * self.settings.max_portfolio_exposure
        current_notional = sum(
            (p.quantity * (context.mark_price or p.current_price) for p in portfolio.open_positions),
            Decimal("0"),
        )
        if current_notional + approved_qty * price > max_port_notional:
            room = max_port_notional - current_notional
            if room <= 0:
                return self._reject(
                    RiskReasonCode.MAX_PORTFOLIO_EXPOSURE, "Portfolio exposure too high", checks
                )
            reduced = (room / price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            if reduced <= 0:
                return self._reject(
                    RiskReasonCode.MAX_PORTFOLIO_EXPOSURE, "Portfolio exposure too high", checks
                )
            approved_qty = reduced
            decision = RiskDecision.REDUCED
            reason = RiskReasonCode.SIZE_REDUCED_BY_RISK

        if approved_qty <= 0:
            return self._reject(RiskReasonCode.INVALID_QUANTITY, "Approved qty is zero", checks)

        # Record acceptance bookkeeping
        self.state.seen_idempotency_keys.add(request.idempotency_key)
        self.state.recent_order_times.append(now)

        return RiskEvaluation(
            decision=decision,
            reason_code=reason,
            approved_quantity=approved_qty,
            message="OK" if decision == RiskDecision.APPROVED else "Size reduced by risk limits",
            checks=checks,
        )

    def open_circuit_breaker(self, reason: str) -> None:
        self.state.circuit_breaker_open = True
        self.state.circuit_breaker_reason = reason

    def close_circuit_breaker(self) -> None:
        self.state.circuit_breaker_open = False
        self.state.circuit_breaker_reason = ""

    def _check_live_gating(
        self, context: RiskContext, checks: dict[str, Any]
    ) -> RiskEvaluation | None:
        """All live gates must pass; any failure blocks."""
        if not (context.live_trading_enabled or self.settings.live_trading_enabled):
            return self._reject(
                RiskReasonCode.LIVE_TRADING_DISABLED, "Live trading disabled", checks
            )
        if context.kill_switch_enabled or self.settings.kill_switch_enabled:
            return self._halt(RiskReasonCode.KILL_SWITCH_ACTIVE, "Kill switch active", checks)
        if not (context.has_exchange_credentials or self.settings.has_exchange_credentials):
            return self._reject(RiskReasonCode.INVALID_CREDENTIALS, "Missing credentials", checks)
        if not self.state.risk_engine_healthy:
            return self._reject(RiskReasonCode.RISK_ENGINE_UNHEALTHY, "Risk unhealthy", checks)
        if not self.state.market_data_healthy:
            return self._reject(RiskReasonCode.MARKET_DATA_UNHEALTHY, "MD unhealthy", checks)
        if not self.state.database_healthy:
            return self._reject(RiskReasonCode.DATABASE_UNHEALTHY, "DB unhealthy", checks)
        if not self.state.reconciliation_healthy:
            return self._reject(
                RiskReasonCode.RECONCILIATION_UNHEALTHY, "Reconciliation unhealthy", checks
            )
        if not context.live_approval_valid:
            return self._reject(
                RiskReasonCode.INVALID_LIVE_APPROVAL, "Live approval token invalid", checks
            )
        checks["live_gating"] = "passed"
        return None

    @staticmethod
    def _reject(code: RiskReasonCode, message: str, checks: dict[str, Any]) -> RiskEvaluation:
        return RiskEvaluation(
            decision=RiskDecision.REJECTED,
            reason_code=code,
            approved_quantity=None,
            message=message,
            checks=checks,
        )

    @staticmethod
    def _halt(code: RiskReasonCode, message: str, checks: dict[str, Any]) -> RiskEvaluation:
        return RiskEvaluation(
            decision=RiskDecision.HALTED,
            reason_code=code,
            approved_quantity=None,
            message=message,
            checks=checks,
        )


# Module-level singleton used by execution gateway — strategies/API must not bypass.
_ENGINE: RiskEngine | None = None


def get_risk_engine() -> RiskEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = RiskEngine()
    return _ENGINE


def reset_risk_engine() -> RiskEngine:
    global _ENGINE
    _ENGINE = RiskEngine()
    return _ENGINE
