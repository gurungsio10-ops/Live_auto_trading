"""
Atlas command-line interface.

`paper-run` executes a safe, public-data (or offline) paper-trading session
through the deterministic orchestrator. It never touches a live-order path:
paper mode is asserted at startup, the kill switch is honoured, and only public
market data endpoints are used (no exchange credentials).

Examples:
    python -m app.cli paper-run --symbol BTC/USDT --interval 1m --strategy ema_trend --duration-minutes 10
    python -m app.cli paper-run --exchange kraken --symbol BTC/USD --duration-minutes 2
    python -m app.cli paper-run --offline --duration-minutes 0     # deterministic, no network
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.time import from_unix_ms, utc_now
from app.db.base import Base, SessionLocal, engine
from app.journal.store import JournalStore
from app.market_data.normalizers.timestamps import normalize_candles
from app.models.domain.market import Candle
from app.services.sample_market import build_sample_candles
from app.services.trading_orchestrator import TradingOrchestrator
from app.strategies.registry import get_strategy

logger = get_logger("cli")

_INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}


def _ccxt_symbol(symbol: str) -> str:
    if "/" in symbol:
        return symbol
    for quote in ("USDT", "USDC", "USD", "EUR", "BTC"):
        if symbol.endswith(quote):
            return f"{symbol[: -len(quote)]}/{quote}"
    return symbol


def _print_banner(args, settings, session_id: str) -> None:
    kill = "ENABLED" if settings.kill_switch_enabled else "disabled"
    print("=" * 68)
    print("  PAPER MODE — SIMULATED FILLS ONLY. NO LIVE ORDERS ARE SUBMITTED.")
    print("=" * 68)
    print(f"  session_id       : {session_id}")
    print(f"  trading_mode     : {settings.trading_mode}")
    print(f"  live_trading     : {settings.live_trading_enabled}")
    print(f"  kill_switch      : {kill}")
    print(
        f"  source           : {'offline sample' if args.offline else args.exchange + ' (public)'}"
    )
    print(f"  symbol           : {args.symbol}")
    print(f"  interval         : {args.interval}")
    print(f"  strategy         : {args.strategy}")
    print(f"  duration_minutes : {args.duration_minutes}")
    print("=" * 68, flush=True)


def _print_summary(snapshot: dict) -> None:
    print("\n" + "-" * 68)
    print("  PAPER-RUN SESSION SUMMARY")
    print("-" * 68)
    order = [
        "session_id",
        "candles_received",
        "candles_rejected",
        "signals_generated",
        "hold_decisions",
        "risk_approvals",
        "risk_rejections",
        "paper_orders",
        "fills",
        "fees",
        "realized_pnl",
        "unrealized_pnl",
        "current_balance",
        "equity",
        "max_drawdown",
        "open_positions",
        "errors",
    ]
    for key in order:
        print(f"  {key:<18}: {snapshot.get(key)}")
    print("-" * 68, flush=True)


async def _fetch_ccxt_candles(
    exchange, symbol: str, interval: str, limit: int
) -> list[Candle]:
    raw = await exchange.fetch_ohlcv(symbol, interval, limit=limit)
    candles: list[Candle] = []
    # Drop the last row: it is usually the still-forming (open) candle.
    for row in raw[:-1] if len(raw) > 1 else raw:
        candles.append(
            Candle(
                symbol=symbol,
                timeframe=interval,
                open_time=from_unix_ms(int(row[0])),
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[5])),
                is_closed=True,
            )
        )
    return normalize_candles(candles)


async def paper_run(args: argparse.Namespace) -> int:
    settings = get_settings()

    # Hard safety gate: never run this command outside paper mode.
    if settings.trading_mode != "paper" or settings.live_trading_enabled:
        print(
            "REFUSING TO RUN: paper-run requires TRADING_MODE=paper and LIVE_TRADING_ENABLED=false"
        )
        return 2

    try:
        strategy = get_strategy(args.strategy)
    except KeyError:
        print(f"Unknown strategy: {args.strategy}")
        return 2

    session_id = uuid4().hex
    _print_banner(args, settings, session_id)

    # Ensure journal tables exist (checkfirst = no-op if migrations ran).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover - non-unix
            pass

    session = SessionLocal()
    journal = JournalStore(session)
    orch = TradingOrchestrator(
        strategy=strategy,
        session_id=session_id,
        settings=settings,
        journal=journal,
        max_candle_age_seconds=args.max_candle_age,
    )

    exchange = None
    try:
        if args.offline:
            for candle in build_sample_candles(args.symbol, args.interval):
                if stop.is_set():
                    break
                await orch.process_candle(candle)
                logger.info(
                    "offline_candle", symbol=candle.symbol, close=str(candle.close)
                )
        else:
            import ccxt.async_support as ccxt

            ccxt_symbol = _ccxt_symbol(args.symbol)
            exchange = getattr(ccxt, args.exchange)({"enableRateLimit": True})
            last_open = None
            # Warm-up with recent history so indicators are ready immediately.
            warm = await _fetch_ccxt_candles(
                exchange, ccxt_symbol, args.interval, args.warmup
            )
            for candle in warm:
                await orch.process_candle(candle)
                last_open = candle.open_time

            deadline = utc_now() + timedelta(minutes=args.duration_minutes)
            poll = args.poll_seconds or min(
                _INTERVAL_SECONDS.get(args.interval, 60), 20
            )
            backoff = 1.0
            while not stop.is_set() and utc_now() < deadline:
                try:
                    latest = await _fetch_ccxt_candles(
                        exchange, ccxt_symbol, args.interval, 3
                    )
                    for candle in latest:
                        if last_open is None or candle.open_time > last_open:
                            await orch.process_candle(candle)
                            last_open = candle.open_time
                    backoff = 1.0
                except Exception as exc:  # noqa: BLE001 - feed errors must not crash the run
                    orch.stats.errors += 1
                    logger.warning(
                        "feed_error", error=type(exc).__name__, detail=str(exc)[:160]
                    )
                    await asyncio.sleep(min(backoff, 30.0))
                    backoff *= 2
                    continue
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll)
                except TimeoutError:
                    pass
    finally:
        if exchange is not None:
            with contextlib.suppress(Exception):
                await exchange.close()
        await session.close()

    _print_summary(orch.snapshot())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="Project Atlas CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    pr = sub.add_parser(
        "paper-run", help="Run a public-data (or offline) paper-trading session"
    )
    pr.add_argument(
        "--symbol", default="BTC/USDT", help="Trading pair, e.g. BTC/USDT or BTCUSDT"
    )
    pr.add_argument("--interval", default="1m", choices=list(_INTERVAL_SECONDS))
    pr.add_argument("--strategy", default="ema_trend")
    pr.add_argument("--duration-minutes", type=int, default=10)
    pr.add_argument(
        "--exchange", default="binance", help="ccxt exchange id for public data"
    )
    pr.add_argument(
        "--warmup", type=int, default=120, help="historical candles to warm up on"
    )
    pr.add_argument("--poll-seconds", type=int, default=0, help="0 = auto")
    pr.add_argument(
        "--max-candle-age",
        type=int,
        default=None,
        help="reject candles older than N seconds",
    )
    pr.add_argument(
        "--offline", action="store_true", help="use deterministic offline sample data"
    )
    pr.set_defaults(func=paper_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging(get_settings().log_level)
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
