#!/usr/bin/env python3
"""
Entry point for the Alpaca paper-trading bot.

Usage
-----
Live (scheduled) mode — runs every market day at 9:45 AM Eastern:
    python main.py --live

Backtest mode — simulates the past 2 years and prints a summary:
    python main.py --backtest
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta, datetime

import pytz
import schedule
import yaml

from src.broker import get_trading_client, get_data_client, fetch_bars, place_market_order, get_positions
from src.strategy import latest_signal
from src.risk import DailyRiskManager
from src.logger import TradeLogger
from src.backtest import run_backtest, print_backtest_results


EASTERN = pytz.timezone("America/New_York")
CONFIG_PATH = "config/config.yaml"


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Live trading session
# ---------------------------------------------------------------------------

def run_trading_session(cfg: dict) -> None:
    """Execute one full trading pass (called by the scheduler)."""
    print(f"\n[{datetime.now(EASTERN).isoformat()}] Starting trading session…")

    trading_client = get_trading_client()
    data_client = get_data_client()
    logger = TradeLogger(cfg["logging"]["csv_path"])

    watchlist: list[str] = cfg["watchlist"]
    short_w: int = cfg["strategy"]["short_window"]
    long_w: int = cfg["strategy"]["long_window"]
    pos_size: float = cfg["position"]["size_usd"]
    max_exposure: float = cfg["risk"]["max_total_exposure_usd"]
    max_loss: float = cfg["risk"]["max_daily_loss_usd"]

    # Fetch start-of-day equity for daily-loss tracking
    account = trading_client.get_account()
    start_equity = float(account.equity)

    risk_mgr = DailyRiskManager(
        start_of_day_equity=start_equity,
        max_daily_loss=max_loss,
        max_total_exposure=max_exposure,
    )

    # Fetch enough history for the long SMA + 1 crossover bar
    end_date = date.today()
    start_date = end_date - timedelta(days=long_w * 2 + 10)

    try:
        bars_df = fetch_bars(data_client, watchlist, start_date, end_date)
    except Exception as exc:
        print(f"[ERROR] Failed to fetch bars: {exc}")
        logger.log("ALL", "ERROR", notes=str(exc))
        return

    current_positions = get_positions(trading_client)

    for symbol in watchlist:
        if risk_mgr.is_halted:
            logger.log(symbol, "SKIP", notes="Risk manager halted for the day")
            break

        try:
            if isinstance(bars_df.index, __import__("pandas").MultiIndex):
                if symbol not in bars_df.index.get_level_values("symbol"):
                    logger.log(symbol, "SKIP", notes="No bar data returned")
                    continue
                prices = bars_df.loc[symbol]["close"]
            else:
                prices = bars_df["close"]

            if len(prices) < long_w + 1:
                logger.log(symbol, "SKIP", notes=f"Insufficient data ({len(prices)} bars)")
                continue

            signal = latest_signal(prices, short_w, long_w)
            logger.log(symbol, signal)

            if signal == "HOLD":
                continue

            # Check whether we already hold this symbol
            has_position = symbol in current_positions

            if signal == "BUY" and has_position:
                logger.log(symbol, "SKIP", notes="Already holding position")
                continue
            if signal == "SELL" and not has_position:
                logger.log(symbol, "SKIP", notes="No position to sell")
                continue

            # Risk check
            account = trading_client.get_account()
            current_equity = float(account.equity)
            trade_amount = pos_size if signal == "BUY" else 0.0

            allowed, reason = risk_mgr.can_trade(
                current_positions, trade_amount, current_equity
            )
            if not allowed:
                logger.log(symbol, "BLOCKED", notes=reason)
                continue

            # Place order
            order = place_market_order(trading_client, symbol, pos_size, signal)
            logger.log(
                symbol,
                signal,
                order_id=order["id"],
                fill_price=order.get("filled_avg_price", ""),
                notes=f"status={order['status']}",
            )

            # Refresh positions after order
            current_positions = get_positions(trading_client)

        except Exception as exc:
            logger.log(symbol, "ERROR", notes=str(exc))
            print(f"[ERROR] {symbol}: {exc}")

    print(f"[{datetime.now(EASTERN).isoformat()}] Session complete.")


# ---------------------------------------------------------------------------
# Backtest mode
# ---------------------------------------------------------------------------

def run_backtest_mode(cfg: dict) -> None:
    print("Fetching 2 years of daily bars for backtest…")
    data_client = get_data_client()

    end_date = date.today()
    start_date = end_date - timedelta(days=365 * 2 + 5)

    watchlist: list[str] = cfg["watchlist"]
    bars_df = fetch_bars(data_client, watchlist, start_date, end_date)

    results = run_backtest(
        bars_df=bars_df,
        watchlist=watchlist,
        short_window=cfg["strategy"]["short_window"],
        long_window=cfg["strategy"]["long_window"],
        position_size_usd=cfg["position"]["size_usd"],
    )
    print_backtest_results(results)


# ---------------------------------------------------------------------------
# Scheduler helpers
# ---------------------------------------------------------------------------

def _is_market_day() -> bool:
    """Very simple check: Mon–Fri. Does not account for holidays."""
    return datetime.now(EASTERN).weekday() < 5


def _scheduled_job(cfg: dict) -> None:
    if _is_market_day():
        run_trading_session(cfg)
    else:
        print(f"[{datetime.now(EASTERN).isoformat()}] Not a market day — skipping.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Alpaca paper-trading bot")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Run live (paper) scheduler")
    group.add_argument("--backtest", action="store_true", help="Run backtest on 2 years of data")
    args = parser.parse_args()

    cfg = load_config()

    if args.backtest:
        run_backtest_mode(cfg)
        return

    # Live mode — schedule at 09:45 Eastern every day
    print("Scheduling live (paper) trading session at 09:45 ET daily.")
    print("Press Ctrl+C to stop.\n")

    schedule.every().day.at("09:45").do(_scheduled_job, cfg=cfg)

    # Run immediately on startup so you don't have to wait until 09:45
    _scheduled_job(cfg)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
