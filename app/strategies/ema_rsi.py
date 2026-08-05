"""
EMA crossover with RSI confirmation — paper MVP baseline strategy.

BUY:  fast EMA crosses above slow EMA AND RSI > 50 AND flat
SELL: fast EMA crosses below slow EMA while long
      (stop-loss / take-profit are risk/orchestrator concerns; strategy
       still attaches suggested levels from STOP_LOSS_PERCENT / TAKE_PROFIT_PERCENT)
HOLD: otherwise / insufficient data

Deterministic. No LLM. Closed candles only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.core.time import utc_now
from app.indicators import ema, rsi
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import TradeSignal
from app.strategies.base import Strategy, StrategyConfig, StrategyContext


class EMARSIStrategy(Strategy):
    strategy_id = "ema_rsi"
    name = "EMA Crossover + RSI"
    version = "1.0.0"

    def default_config(self) -> StrategyConfig:
        settings = get_settings()
        return StrategyConfig(
            strategy_id=self.strategy_id,
            version=self.version,
            params={
                "fast_ema": settings.fast_ema_period,
                "slow_ema": settings.slow_ema_period,
                "rsi_period": settings.rsi_period,
                "rsi_buy_min": "50",
                "warmup_margin": 5,
                "stop_loss_percent": str(settings.stop_loss_percent),
                "take_profit_percent": str(settings.take_profit_percent),
            },
        )

    def evaluate(self, context: StrategyContext) -> TradeSignal:
        params = {**self.default_config().params, **context.config.params}
        candles = context.candles
        symbol = candles[-1].symbol if candles else "UNKNOWN"
        timeframe = candles[-1].timeframe if candles else "1m"
        fp = self.fingerprint(candles, params)
        fast_p = int(params["fast_ema"])
        slow_p = int(params["slow_ema"])
        rsi_p = int(params["rsi_period"])
        need = max(slow_p, rsi_p) + int(params["warmup_margin"]) + 1
        calc_ts = utc_now()
        candle_ts = candles[-1].open_time if candles else calc_ts

        if len(candles) < need:
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.HOLD,
                fp,
                f"insufficient history ({len(candles)} < {need})",
                Decimal("0"),
                {},
                candle_ts,
                calc_ts,
            )

        closes = [c.close for c in candles]
        fast = ema(closes, fast_p)
        slow = ema(closes, slow_p)
        rsi_series = rsi(closes, rsi_p)
        i = len(closes) - 1
        f_cur, f_prev = fast[i], fast[i - 1]
        s_cur, s_prev = slow[i], slow[i - 1]
        r_cur = rsi_series[i]
        if None in (f_cur, f_prev, s_cur, s_prev, r_cur):
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.HOLD,
                fp,
                "indicators not ready",
                Decimal("0"),
                {},
                candle_ts,
                calc_ts,
            )

        assert f_cur is not None and f_prev is not None
        assert s_cur is not None and s_prev is not None and r_cur is not None
        rsi_min = Decimal(str(params["rsi_buy_min"]))
        indicators: dict[str, Any] = {
            "fast_ema": str(f_cur),
            "slow_ema": str(s_cur),
            "fast_ema_prev": str(f_prev),
            "slow_ema_prev": str(s_prev),
            "rsi": str(r_cur),
            "close": str(closes[i]),
        }
        has_long = context.position is not None and context.position.quantity > 0
        cross_up = f_prev <= s_prev and f_cur > s_cur
        cross_down = f_prev >= s_prev and f_cur < s_cur

        if cross_up and r_cur > rsi_min and not has_long:
            close = closes[i]
            sl_pct = Decimal(str(params["stop_loss_percent"])) / Decimal("100")
            tp_pct = Decimal(str(params["take_profit_percent"])) / Decimal("100")
            stop = close * (Decimal("1") - sl_pct)
            target = close * (Decimal("1") + tp_pct)
            indicators["suggested_stop"] = str(stop)
            indicators["suggested_target"] = str(target)
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.BUY,
                fp,
                f"fast EMA crossed above slow EMA with RSI {r_cur} > {rsi_min}",
                Decimal("1"),
                indicators,
                candle_ts,
                calc_ts,
                entry=close,
                stop=stop,
                target=target,
            )
        if cross_down and has_long:
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.SELL,
                fp,
                "fast EMA crossed below slow EMA while long",
                Decimal("1"),
                indicators,
                candle_ts,
                calc_ts,
            )
        reason = "no EMA+RSI setup"
        if cross_up and r_cur <= rsi_min:
            reason = f"EMA cross up ignored — RSI {r_cur} <= {rsi_min}"
        elif cross_up and has_long:
            reason = "EMA cross up ignored — already long"
        return self._sig(
            symbol,
            timeframe,
            SignalDirection.HOLD,
            fp,
            reason,
            Decimal("0.5"),
            indicators,
            candle_ts,
            calc_ts,
        )

    def _sig(
        self,
        symbol: str,
        timeframe: str,
        direction: SignalDirection,
        fp: str,
        reason: str,
        confidence: Decimal,
        indicators: dict[str, Any],
        candle_ts: Any,
        calc_ts: Any,
        entry: Decimal | None = None,
        stop: Decimal | None = None,
        target: Decimal | None = None,
    ) -> TradeSignal:
        return TradeSignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol=symbol,
            timestamp=calc_ts,
            direction=direction,
            confidence=confidence,
            entry_rationale=reason,
            invalidation_condition="opposite EMA cross or risk halt",
            suggested_entry=entry,
            suggested_stop=stop,
            suggested_target=target,
            input_data_fingerprint=fp,
            metadata={
                "timeframe": timeframe,
                "action": direction.value.upper()
                if direction != SignalDirection.HOLD
                else "HOLD",
                "candle_timestamp": getattr(
                    candle_ts, "isoformat", lambda: str(candle_ts)
                )(),
                "calculation_timestamp": getattr(
                    calc_ts, "isoformat", lambda: str(calc_ts)
                )(),
                "indicators": indicators,
                "indicator_snapshot": indicators,
                "reference_price": indicators.get("close"),
                "confidence_kind": "rule_derived_not_predictive",
            },
        )
