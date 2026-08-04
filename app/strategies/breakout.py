"""Donchian-style breakout strategy — long-only, closed candles only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.time import utc_now
from app.indicators import atr
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import TradeSignal
from app.strategies.base import Strategy, StrategyConfig, StrategyContext


class BreakoutStrategy(Strategy):
    """
    BUY when close breaks above the prior N-bar high (excluding current bar).
    SELL when close breaks below the prior N-bar low while long.
    ATR used for suggested stop distance.
    """

    strategy_id = "breakout"
    name = "Donchian Breakout"
    version = "1.0.0"

    DEFAULT_PARAMS: dict[str, Any] = {
        "lookback": 20,
        "atr_period": 14,
        "atr_stop_mult": "1.5",
        "warmup_margin": 2,
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
        lookback = int(params["lookback"])
        need = lookback + int(params["warmup_margin"]) + 1
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

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        i = len(closes) - 1
        # Prior window excludes the current closed bar (no same-bar look-ahead).
        window_highs = highs[i - lookback : i]
        window_lows = lows[i - lookback : i]
        prior_high = max(window_highs)
        prior_low = min(window_lows)
        atr_series = atr(highs, lows, closes, int(params["atr_period"]))
        atr_cur = atr_series[i]
        close = closes[i]

        indicators: dict[str, Any] = {
            "close": str(close),
            "prior_high": str(prior_high),
            "prior_low": str(prior_low),
            "lookback": lookback,
        }
        if atr_cur is not None:
            indicators["atr"] = str(atr_cur)

        has_long = context.position is not None and context.position.quantity > 0
        if close > prior_high and not has_long:
            stop = None
            if atr_cur is not None and atr_cur > 0:
                stop = close - atr_cur * Decimal(str(params["atr_stop_mult"]))
                indicators["suggested_stop"] = str(stop)
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.BUY,
                fp,
                f"close broke above prior {lookback}-bar high {prior_high}",
                Decimal("1"),
                indicators,
                candle_ts,
                calc_ts,
                entry=close,
                stop=stop,
            )
        if close < prior_low and has_long:
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.SELL,
                fp,
                f"close broke below prior {lookback}-bar low {prior_low}",
                Decimal("1"),
                indicators,
                candle_ts,
                calc_ts,
            )
        return self._sig(
            symbol,
            timeframe,
            SignalDirection.HOLD,
            fp,
            "inside Donchian channel",
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
    ) -> TradeSignal:
        return TradeSignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol=symbol,
            timestamp=calc_ts,
            direction=direction,
            confidence=confidence,
            entry_rationale=reason,
            invalidation_condition="opposite channel break or risk halt",
            suggested_entry=entry,
            suggested_stop=stop,
            input_data_fingerprint=fp,
            metadata={
                "timeframe": timeframe,
                "candle_timestamp": getattr(
                    candle_ts, "isoformat", lambda: str(candle_ts)
                )(),
                "calculation_timestamp": getattr(
                    calc_ts, "isoformat", lambda: str(calc_ts)
                )(),
                "indicators": indicators,
                "confidence_kind": "rule_derived_not_predictive",
            },
        )
