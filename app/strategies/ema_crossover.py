"""
Deterministic EMA crossover strategy (long-only spot).

Rules (closed candles only — caller must not pass incomplete bars):
- BUY:  previous fast <= previous slow AND current fast > current slow,
        and no existing long position.
- SELL: previous fast >= previous slow AND current fast < current slow,
        and an existing long position.
- HOLD: otherwise (including insufficient history).

Defaults: fast=9, slow=21. Confidence is rule-derived, not predictive.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.time import utc_now
from app.indicators import atr, ema, rsi
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import TradeSignal
from app.strategies.base import Strategy, StrategyConfig, StrategyContext


class EMACrossoverStrategy(Strategy):
    """Minimal long-only EMA crossover — no RSI/ATR/volume filters."""

    strategy_id = "ema_crossover"
    name = "EMA Crossover"
    version = "1.1.0"

    DEFAULT_PARAMS: dict[str, Any] = {
        "fast_ema": 9,
        "slow_ema": 21,
        "warmup_margin": 5,
        # Optional RSI confirmation (off by default — keeps fixture BUY deterministic).
        "use_rsi_filter": False,
        "rsi_period": 14,
        "rsi_buy_min": 45,
        # ATR-based stop + fixed reward:risk target on BUY signals.
        "use_atr_stop": True,
        "atr_period": 14,
        "atr_stop_mult": "1.5",
        "reward_risk": "2",
    }

    def default_config(self) -> StrategyConfig:
        return StrategyConfig(
            strategy_id=self.strategy_id,
            version=self.version,
            params=dict(self.DEFAULT_PARAMS),
        )

    def evaluate(self, context: StrategyContext) -> TradeSignal:
        params = {**self.DEFAULT_PARAMS, **context.config.params}
        candles = context.candles
        symbol = candles[-1].symbol if candles else "UNKNOWN"
        timeframe = candles[-1].timeframe if candles else "1m"
        fp = self.fingerprint(candles, params)
        fast_period = int(params["fast_ema"])
        slow_period = int(params["slow_ema"])
        warmup = int(params["warmup_margin"])
        min_history = slow_period + warmup

        calc_ts = utc_now()
        candle_ts = candles[-1].open_time if candles else calc_ts

        if len(candles) < min_history:
            return self._signal(
                symbol=symbol,
                timeframe=timeframe,
                direction=SignalDirection.HOLD,
                fp=fp,
                reason=f"insufficient history ({len(candles)} < {min_history})",
                confidence=Decimal("0"),
                indicators={},
                candle_ts=candle_ts,
                calc_ts=calc_ts,
            )

        # Reject non-monotonic open times (invalid ordering / duplicates).
        times = [c.open_time for c in candles]
        if len(times) != len(set(times)):
            return self._signal(
                symbol=symbol,
                timeframe=timeframe,
                direction=SignalDirection.HOLD,
                fp=fp,
                reason="duplicate candle open_time in window",
                confidence=Decimal("0"),
                indicators={},
                candle_ts=candle_ts,
                calc_ts=calc_ts,
            )
        if any(times[i] >= times[i + 1] for i in range(len(times) - 1)):
            return self._signal(
                symbol=symbol,
                timeframe=timeframe,
                direction=SignalDirection.HOLD,
                fp=fp,
                reason="candles not strictly increasing by open_time",
                confidence=Decimal("0"),
                indicators={},
                candle_ts=candle_ts,
                calc_ts=calc_ts,
            )

        closes = [c.close for c in candles]
        fast = ema(closes, fast_period)
        slow = ema(closes, slow_period)
        i = len(closes) - 1
        fast_cur, slow_cur = fast[i], slow[i]
        fast_prev, slow_prev = fast[i - 1], slow[i - 1]
        if None in (fast_cur, slow_cur, fast_prev, slow_prev):
            return self._signal(
                symbol=symbol,
                timeframe=timeframe,
                direction=SignalDirection.HOLD,
                fp=fp,
                reason="indicators not ready",
                confidence=Decimal("0"),
                indicators={},
                candle_ts=candle_ts,
                calc_ts=calc_ts,
            )
        assert (
            fast_cur is not None
            and slow_cur is not None
            and fast_prev is not None
            and slow_prev is not None
        )

        indicators = {
            "fast_ema": str(fast_cur),
            "slow_ema": str(slow_cur),
            "fast_ema_prev": str(fast_prev),
            "slow_ema_prev": str(slow_prev),
            "close": str(closes[i]),
            "confidence_kind": "rule_derived",
        }
        has_long = context.position is not None and context.position.quantity > 0

        # Optional RSI / ATR snapshots (no look-ahead — closed candles only).
        rsi_period = int(params.get("rsi_period", 14))
        atr_period = int(params.get("atr_period", 14))
        rsi_series = rsi(closes, rsi_period)
        atr_series = atr(
            [c.high for c in candles],
            [c.low for c in candles],
            closes,
            atr_period,
        )
        rsi_cur = rsi_series[i]
        atr_cur = atr_series[i]
        if rsi_cur is not None:
            indicators["rsi"] = str(rsi_cur)
        if atr_cur is not None:
            indicators["atr"] = str(atr_cur)

        crossed_up = fast_prev <= slow_prev and fast_cur > slow_cur
        crossed_down = fast_prev >= slow_prev and fast_cur < slow_cur

        if crossed_up and not has_long:
            if bool(params.get("use_rsi_filter")) and rsi_cur is not None:
                rsi_min = Decimal(str(params.get("rsi_buy_min", 45)))
                if rsi_cur < rsi_min:
                    return self._signal(
                        symbol=symbol,
                        timeframe=timeframe,
                        direction=SignalDirection.HOLD,
                        fp=fp,
                        reason=f"EMA cross up but RSI {rsi_cur} < {rsi_min}",
                        confidence=Decimal("0.25"),
                        indicators=indicators,
                        candle_ts=candle_ts,
                        calc_ts=calc_ts,
                    )
            stop = None
            target = None
            if bool(params.get("use_atr_stop")) and atr_cur is not None and atr_cur > 0:
                mult = Decimal(str(params.get("atr_stop_mult", "1.5")))
                rr = Decimal(str(params.get("reward_risk", "2")))
                stop = closes[i] - (atr_cur * mult)
                target = closes[i] + (atr_cur * mult * rr)
                indicators["suggested_stop"] = str(stop)
                indicators["suggested_target"] = str(target)
            return self._signal(
                symbol=symbol,
                timeframe=timeframe,
                direction=SignalDirection.BUY,
                fp=fp,
                reason=(
                    f"fast EMA({fast_period}) crossed above slow EMA({slow_period}); "
                    "no existing long"
                ),
                confidence=Decimal("1"),
                indicators=indicators,
                candle_ts=candle_ts,
                calc_ts=calc_ts,
                entry=closes[i],
                stop=stop,
                target=target,
            )

        if crossed_down and has_long:
            return self._signal(
                symbol=symbol,
                timeframe=timeframe,
                direction=SignalDirection.SELL,
                fp=fp,
                reason=(
                    f"fast EMA({fast_period}) crossed below slow EMA({slow_period}); "
                    "exit long"
                ),
                confidence=Decimal("1"),
                indicators=indicators,
                candle_ts=candle_ts,
                calc_ts=calc_ts,
            )

        if crossed_up and has_long:
            reason = "crossover up ignored — already long"
        elif crossed_down and not has_long:
            reason = "crossover down ignored — flat"
        else:
            reason = "no EMA crossover on closed candle"
        return self._signal(
            symbol=symbol,
            timeframe=timeframe,
            direction=SignalDirection.HOLD,
            fp=fp,
            reason=reason,
            confidence=Decimal("0.5"),
            indicators=indicators,
            candle_ts=candle_ts,
            calc_ts=calc_ts,
        )

    def _signal(
        self,
        *,
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
            invalidation_condition="opposite EMA crossover or risk halt",
            suggested_entry=entry,
            suggested_stop=stop,
            suggested_target=target,
            input_data_fingerprint=fp,
            metadata={
                "timeframe": timeframe,
                "candle_timestamp": candle_ts.isoformat()
                if hasattr(candle_ts, "isoformat")
                else str(candle_ts),
                "calculation_timestamp": calc_ts.isoformat()
                if hasattr(calc_ts, "isoformat")
                else str(calc_ts),
                "indicators": indicators,
                "confidence_kind": "rule_derived_not_predictive",
            },
        )
