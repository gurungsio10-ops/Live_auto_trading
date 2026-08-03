"""Candle continuity, duplicate, missing, and OHLC sanity validators."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from app.core.time import ensure_utc
from app.models.domain.market import Candle

TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}


@dataclass
class ValidationIssue:
    code: str
    message: str
    index: int | None = None


@dataclass
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    missing_timestamps: list = field(default_factory=list)
    duplicate_timestamps: list = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return self.issues


class CandleValidationError(ValueError):
    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        super().__init__(f"Candle validation failed: {[i.code for i in result.issues]}")


def validate_ohlc_sanity(
    candle: Candle, *, index: int | None = None
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if candle.low > candle.open or candle.low > candle.close:
        issues.append(
            ValidationIssue("OHLC_LOW_INVALID", "low must be <= open and close", index)
        )
    if candle.high < candle.open or candle.high < candle.close:
        issues.append(
            ValidationIssue(
                "OHLC_HIGH_INVALID", "high must be >= open and close", index
            )
        )
    if candle.high < candle.low:
        issues.append(ValidationIssue("OHLC_HIGH_LT_LOW", "high must be >= low", index))
    if candle.volume < Decimal("0"):
        issues.append(ValidationIssue("VOLUME_NEGATIVE", "volume must be >= 0", index))
    if any(v < 0 for v in (candle.open, candle.high, candle.low, candle.close)):
        issues.append(ValidationIssue("PRICE_NEGATIVE", "prices must be >= 0", index))
    return issues


def validate_candles(
    candles: list[Candle],
    *,
    timeframe: str | None = None,
    raise_on_error: bool = False,
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    duplicates: list = []
    missing: list = []

    if not candles:
        result = ValidationResult(
            ok=True, issues=[], missing_timestamps=[], duplicate_timestamps=[]
        )
        return result

    tf = timeframe or candles[0].timeframe
    delta = TIMEFRAME_DELTAS.get(tf)
    if delta is None:
        issues.append(
            ValidationIssue("UNSUPPORTED_TIMEFRAME", f"Unknown timeframe: {tf}")
        )

    seen: dict = {}
    sorted_candles = sorted(candles, key=lambda c: ensure_utc(c.open_time))

    for idx, candle in enumerate(sorted_candles):
        issues.extend(validate_ohlc_sanity(candle, index=idx))
        ts = ensure_utc(candle.open_time)
        if ts in seen:
            duplicates.append(ts)
            issues.append(
                ValidationIssue(
                    "DUPLICATE_CANDLE", f"Duplicate open_time {ts.isoformat()}", idx
                )
            )
        seen[ts] = idx

        if delta is not None and idx > 0:
            prev = ensure_utc(sorted_candles[idx - 1].open_time)
            expected = prev + delta
            if ts > expected:
                cursor = expected
                while cursor < ts:
                    missing.append(cursor)
                    issues.append(
                        ValidationIssue(
                            "MISSING_CANDLE",
                            f"Missing candle at {cursor.isoformat()}",
                            idx,
                        )
                    )
                    cursor += delta
            elif ts < expected:
                issues.append(
                    ValidationIssue(
                        "CONTINUITY_REGRESSION",
                        f"Candle time went backwards at index {idx}",
                        idx,
                    )
                )

    result = ValidationResult(
        ok=len(issues) == 0,
        issues=issues,
        missing_timestamps=missing,
        duplicate_timestamps=duplicates,
    )
    if raise_on_error and not result.ok:
        raise CandleValidationError(result)
    return result
