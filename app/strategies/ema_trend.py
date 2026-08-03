"""EMA Trend Strategy — deterministic rules, no LLM."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.time import utc_now
from app.indicators import atr, ema, rsi, volume_ma
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import TradeSignal
from app.strategies.base import Strategy, StrategyConfig, StrategyContext


class EMATrendStrategy(Strategy):
    """
    Entry (long):
      - fast EMA > slow EMA
      - close > slow EMA
      - RSI in [rsi_min, rsi_max] (non-overbought band)
      - ATR >= min_atr
      - volume > volume MA

    Exit:
      - fast EMA cross under slow EMA
      - stop-loss / take-profit (suggested; engine enforces)
      - max holding period exceeded
    """

    strategy_id = "ema_trend"
    name = "EMA Trend Strategy"
    version = "1.0.0"

    DEFAULT_PARAMS: dict[str, Any] = {
        "fast_ema": 12,
        "slow_ema": 26,
        "rsi_period": 14,
        "rsi_min": "40",
        "rsi_max": "70",
        "atr_period": 14,
        "min_atr": "0.5",
        "volume_ma_period": 20,
        "stop_atr_multiple": "1.5",
        "target_atr_multiple": "3.0",
        "max_holding_bars": 48,
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
        fp = self.fingerprint(candles, params)

        if len(candles) < int(params["slow_ema"]) + 2:
            return self._hold(symbol, fp, "insufficient history")

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]

        fast_period = int(params["fast_ema"])
        slow_period = int(params["slow_ema"])
        fast = ema(closes, fast_period)
        slow = ema(closes, slow_period)
        r = rsi(closes, int(params["rsi_period"]))
        a = atr(highs, lows, closes, int(params["atr_period"]))
        vma = volume_ma(volumes, int(params["volume_ma_period"]))

        i = len(closes) - 1
        fast_cur, slow_cur = fast[i], slow[i]
        fast_prev, slow_prev = fast[i - 1], slow[i - 1]
        rsi_cur, atr_val, vma_cur = r[i], a[i], vma[i]
        if None in (
            fast_cur,
            slow_cur,
            rsi_cur,
            atr_val,
            vma_cur,
            fast_prev,
            slow_prev,
        ):
            return self._hold(symbol, fp, "indicators not ready")
        assert (
            fast_cur is not None
            and slow_cur is not None
            and rsi_cur is not None
            and atr_val is not None
            and vma_cur is not None
            and fast_prev is not None
            and slow_prev is not None
        )

        price = closes[i]
        stop_mult = Decimal(str(params["stop_atr_multiple"]))
        target_mult = Decimal(str(params["target_atr_multiple"]))
        stop = price - atr_val * stop_mult
        target = price + atr_val * target_mult

        # Exit rules when in a position
        if context.position is not None and context.position.quantity > 0:
            bars_held = int(context.indicators.get("bars_held", 0))
            cross_under = fast_prev >= slow_prev and fast_cur < slow_cur
            hit_stop = (
                context.position.stop_loss is not None
                and price <= context.position.stop_loss
            )
            hit_target = (
                context.position.take_profit is not None
                and price >= context.position.take_profit
            )
            max_hold = bars_held >= int(params["max_holding_bars"])
            if cross_under or hit_stop or hit_target or max_hold:
                reason = (
                    "ema cross-under"
                    if cross_under
                    else (
                        "stop-loss"
                        if hit_stop
                        else "take-profit"
                        if hit_target
                        else "max holding period"
                    )
                )
                return TradeSignal(
                    strategy_name=self.name,
                    strategy_version=self.version,
                    symbol=symbol,
                    timestamp=utc_now(),
                    direction=SignalDirection.EXIT,
                    confidence=Decimal("0.8"),
                    entry_rationale=f"Exit: {reason}",
                    invalidation_condition="n/a",
                    suggested_stop=stop,
                    suggested_target=target,
                    suggested_entry=price,
                    input_data_fingerprint=fp,
                    metadata={"exit_reason": reason},
                )
            return self._hold(symbol, fp, "position open, no exit trigger")

        # Entry rules
        rsi_min = Decimal(str(params["rsi_min"]))
        rsi_max = Decimal(str(params["rsi_max"]))
        min_atr = Decimal(str(params["min_atr"]))
        trend_up = fast_cur > slow_cur and price > slow_cur
        rsi_ok = rsi_min <= rsi_cur <= rsi_max
        atr_ok = atr_val >= min_atr
        vol_ok = volumes[i] > vma_cur

        if trend_up and rsi_ok and atr_ok and vol_ok:
            return TradeSignal(
                strategy_name=self.name,
                strategy_version=self.version,
                symbol=symbol,
                timestamp=utc_now(),
                direction=SignalDirection.BUY,
                confidence=Decimal("0.75"),
                entry_rationale=(
                    "fast EMA > slow EMA, price > slow EMA, RSI in range, "
                    "ATR above minimum, volume above volume MA"
                ),
                invalidation_condition="fast EMA crosses under slow EMA or stop hit",
                suggested_stop=stop,
                suggested_target=target,
                suggested_entry=price,
                input_data_fingerprint=fp,
            )

        return self._hold(symbol, fp, "entry filters not met")

    def _hold(self, symbol: str, fp: str, reason: str) -> TradeSignal:
        return TradeSignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol=symbol,
            timestamp=utc_now(),
            direction=SignalDirection.HOLD,
            confidence=Decimal("0"),
            entry_rationale=reason,
            invalidation_condition="n/a",
            input_data_fingerprint=fp,
            metadata={"hold_reason": reason},
        )
