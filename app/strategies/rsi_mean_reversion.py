"""RSI mean-reversion strategy — long-only, deterministic, closed candles only."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.time import utc_now
from app.indicators import rsi
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import TradeSignal
from app.strategies.base import Strategy, StrategyConfig, StrategyContext


class RSIMeanReversionStrategy(Strategy):
    """
    BUY when RSI crosses up through oversold threshold while flat.
    SELL when RSI crosses down through overbought threshold while long.
    """

    strategy_id = "rsi_mean_reversion"
    name = "RSI Mean Reversion"
    version = "1.0.0"

    DEFAULT_PARAMS: dict[str, Any] = {
        "rsi_period": 14,
        "oversold": "30",
        "overbought": "70",
        "warmup_margin": 5,
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
        period = int(params["rsi_period"])
        need = period + int(params["warmup_margin"]) + 1
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
        series = rsi(closes, period)
        i = len(closes) - 1
        cur, prev = series[i], series[i - 1]
        if cur is None or prev is None:
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.HOLD,
                fp,
                "RSI not ready",
                Decimal("0"),
                {},
                candle_ts,
                calc_ts,
            )

        oversold = Decimal(str(params["oversold"]))
        overbought = Decimal(str(params["overbought"]))
        indicators = {
            "rsi": str(cur),
            "rsi_prev": str(prev),
            "oversold": str(oversold),
            "overbought": str(overbought),
            "close": str(closes[i]),
        }
        has_long = context.position is not None and context.position.quantity > 0

        if prev <= oversold < cur and not has_long:
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.BUY,
                fp,
                f"RSI crossed up through oversold {oversold}",
                Decimal("1"),
                indicators,
                candle_ts,
                calc_ts,
                entry=closes[i],
            )
        if prev >= overbought > cur and has_long:
            return self._sig(
                symbol,
                timeframe,
                SignalDirection.SELL,
                fp,
                f"RSI crossed down through overbought {overbought}",
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
            "no RSI mean-reversion cross",
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
    ) -> TradeSignal:
        return TradeSignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol=symbol,
            timestamp=calc_ts,
            direction=direction,
            confidence=confidence,
            entry_rationale=reason,
            invalidation_condition="opposite RSI cross or risk halt",
            suggested_entry=entry,
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
