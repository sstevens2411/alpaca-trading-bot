"""
Backtest engine.

Runs the SMA crossover strategy on the past 2 years of daily bars
and reports: total return %, number of trades, max drawdown %.

Assumptions
-----------
- Each BUY allocates *position_size_usd* from cash.
- Each SELL closes the position at today's close price.
- No partial fills, no slippage, no commissions.
- Only one open position per ticker at a time.
- Short-selling is not modelled (SELL only closes an existing long).
"""

from __future__ import annotations

import pandas as pd
from datetime import date, timedelta

from src.strategy import generate_signals


def run_backtest(
    bars_df: pd.DataFrame,
    watchlist: list[str],
    short_window: int,
    long_window: int,
    position_size_usd: float,
    start_capital: float = 10_000.0,
) -> dict:
    """
    Parameters
    ----------
    bars_df         : MultiIndex DataFrame (symbol, timestamp) with a 'close' column,
                      as returned by alpaca-py's get_stock_bars().df
    watchlist       : list of tickers to trade
    short_window    : SMA short period
    long_window     : SMA long period
    position_size_usd : dollars allocated per BUY
    start_capital   : starting cash

    Returns
    -------
    dict with keys: total_return_pct, num_trades, max_drawdown_pct, trade_log
    """
    cash = start_capital
    # {symbol: {"shares": float, "cost": float}}
    open_positions: dict[str, dict] = {}
    trade_log: list[dict] = []

    # Normalise index: works whether bars_df has a MultiIndex or a plain index.
    if isinstance(bars_df.index, pd.MultiIndex):
        df = bars_df[["close"]].copy()
    else:
        # Single-symbol case
        df = bars_df[["close"]].copy()
        df.index = pd.MultiIndex.from_tuples(
            [(bars_df.index.get_level_values(0)[0], t) for t in bars_df.index],
            names=["symbol", "timestamp"],
        )

    portfolio_values: list[float] = []

    # Collect all unique trading dates across all symbols
    all_dates = sorted(
        df.index.get_level_values("timestamp").normalize().unique()
    )

    for today in all_dates:
        for symbol in watchlist:
            if symbol not in df.index.get_level_values("symbol"):
                continue

            sym_df = df.loc[symbol]
            # Only use bars up to and including today
            sym_today = sym_df[sym_df.index.normalize() <= today]
            if len(sym_today) < long_window + 1:
                continue

            prices = sym_today["close"]
            signals = generate_signals(prices, short_window, long_window)
            signal = signals.iloc[-1]
            close_price = float(prices.iloc[-1])

            if signal == "BUY" and symbol not in open_positions:
                shares = position_size_usd / close_price
                cost = shares * close_price
                if cash >= cost:
                    cash -= cost
                    open_positions[symbol] = {"shares": shares, "cost": cost}
                    trade_log.append(
                        {
                            "date": str(today.date()),
                            "symbol": symbol,
                            "action": "BUY",
                            "price": close_price,
                            "shares": shares,
                        }
                    )

            elif signal == "SELL" and symbol in open_positions:
                pos = open_positions.pop(symbol)
                proceeds = pos["shares"] * close_price
                cash += proceeds
                trade_log.append(
                    {
                        "date": str(today.date()),
                        "symbol": symbol,
                        "action": "SELL",
                        "price": close_price,
                        "shares": pos["shares"],
                        "pnl": proceeds - pos["cost"],
                    }
                )

        # Mark open positions to market
        open_value = 0.0
        for symbol, pos in open_positions.items():
            if symbol in df.index.get_level_values("symbol"):
                sym_df = df.loc[symbol]
                sym_today = sym_df[sym_df.index.normalize() <= today]
                if not sym_today.empty:
                    open_value += pos["shares"] * float(sym_today["close"].iloc[-1])
        portfolio_values.append(cash + open_value)

    # Close any remaining positions at the last available price
    for symbol, pos in open_positions.items():
        if symbol in df.index.get_level_values("symbol"):
            sym_df = df.loc[symbol]
            last_price = float(sym_df["close"].iloc[-1])
            cash += pos["shares"] * last_price

    final_value = cash
    total_return_pct = (final_value - start_capital) / start_capital * 100

    # Max drawdown
    pv = pd.Series(portfolio_values)
    rolling_max = pv.cummax()
    drawdown = (pv - rolling_max) / rolling_max * 100
    max_drawdown_pct = float(drawdown.min())

    return {
        "start_capital": start_capital,
        "final_value": final_value,
        "total_return_pct": round(total_return_pct, 2),
        "num_trades": len(trade_log),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "trade_log": trade_log,
    }


def print_backtest_results(results: dict) -> None:
    print("\n" + "=" * 50)
    print("  BACKTEST RESULTS")
    print("=" * 50)
    print(f"  Starting capital : ${results['start_capital']:,.2f}")
    print(f"  Final value      : ${results['final_value']:,.2f}")
    print(f"  Total return     : {results['total_return_pct']:+.2f}%")
    print(f"  Number of trades : {results['num_trades']}")
    print(f"  Max drawdown     : {results['max_drawdown_pct']:.2f}%")
    print("=" * 50 + "\n")
