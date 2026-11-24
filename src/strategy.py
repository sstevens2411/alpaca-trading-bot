"""
SMA crossover strategy — pure functions, no I/O.

Signal rules
------------
- BUY  : short SMA crosses above long SMA (previous bar: short <= long,
                                            current bar:  short >  long)
- SELL : short SMA crosses below long SMA (previous bar: short >= long,
                                            current bar:  short <  long)
- HOLD : no crossover
"""

from __future__ import annotations

import pandas as pd


def compute_sma(prices: pd.Series, window: int) -> pd.Series:
    """Return the simple moving average of *prices* over *window* periods."""
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    return prices.rolling(window=window).mean()


def generate_signals(
    prices: pd.Series,
    short_window: int = 20,
    long_window: int = 50,
) -> pd.Series:
    """
    Given a price series (DatetimeIndex, ascending), return a signal series:
      'BUY' | 'SELL' | 'HOLD'

    At least *long_window* + 1 data points are required to produce a
    non-HOLD signal (the extra point is needed to detect a crossover).
    """
    if short_window >= long_window:
        raise ValueError(
            f"short_window ({short_window}) must be less than long_window ({long_window})"
        )

    short_sma = compute_sma(prices, short_window)
    long_sma = compute_sma(prices, long_window)

    # Previous position: +1 if short > long, -1 if short < long, 0 if equal
    above = (short_sma > long_sma).astype(int)
    prev_above = above.shift(1)

    signals = pd.Series("HOLD", index=prices.index)

    # BUY: was not above (<=) → now above (>)
    buy_mask = (prev_above == 0) & (above == 1)
    # SELL: was above (>) → now not above (<=)
    sell_mask = (prev_above == 1) & (above == 0)

    signals[buy_mask] = "BUY"
    signals[sell_mask] = "SELL"

    return signals


def latest_signal(
    prices: pd.Series,
    short_window: int = 20,
    long_window: int = 50,
) -> str:
    """Return the signal for the most recent bar only."""
    signals = generate_signals(prices, short_window, long_window)
    return signals.iloc[-1]
