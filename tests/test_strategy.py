"""Unit tests for strategy.py — no network calls."""

import pytest
import pandas as pd
import numpy as np

from src.strategy import compute_sma, generate_signals, latest_signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prices(values: list[float]) -> pd.Series:
    idx = pd.date_range("2023-01-01", periods=len(values), freq="B")
    return pd.Series(values, index=idx, dtype=float)


def _rising_then_falling(n: int = 100) -> pd.Series:
    """Prices that rise for n//2 bars then fall — guarantees a crossover."""
    up = list(range(1, n // 2 + 1))
    down = list(range(n // 2, 0, -1))
    return _make_prices((up + down)[:n])


# ---------------------------------------------------------------------------
# compute_sma
# ---------------------------------------------------------------------------

class TestComputeSMA:
    def test_basic_average(self):
        prices = _make_prices([1, 2, 3, 4, 5])
        sma = compute_sma(prices, 3)
        assert sma.iloc[2] == pytest.approx(2.0)
        assert sma.iloc[4] == pytest.approx(4.0)

    def test_first_values_are_nan(self):
        prices = _make_prices([1, 2, 3, 4, 5])
        sma = compute_sma(prices, 3)
        assert pd.isna(sma.iloc[0])
        assert pd.isna(sma.iloc[1])

    def test_window_1_equals_prices(self):
        prices = _make_prices([10, 20, 30])
        sma = compute_sma(prices, 1)
        pd.testing.assert_series_equal(sma, prices, check_names=False)

    def test_invalid_window_raises(self):
        prices = _make_prices([1, 2, 3])
        with pytest.raises(ValueError):
            compute_sma(prices, 0)


# ---------------------------------------------------------------------------
# generate_signals
# ---------------------------------------------------------------------------

class TestGenerateSignals:
    def test_returns_series_same_length(self):
        prices = _make_prices(list(range(1, 61)))
        signals = generate_signals(prices, 5, 10)
        assert len(signals) == len(prices)

    def test_all_hold_when_insufficient_data(self):
        # 49 bars < long_window=50 → long SMA is never computed, no signal possible
        prices = _make_prices(list(range(1, 50)))
        signals = generate_signals(prices, 5, 50)
        assert (signals == "HOLD").all()

    def test_buy_signal_on_golden_cross(self):
        # Craft prices: flat then jump — short SMA crosses above long SMA
        flat = [100.0] * 60
        flat_series = _make_prices(flat)
        # Inject a sharp rise at bar 55 to force short SMA above long SMA
        rising = flat.copy()
        for i in range(50, 60):
            rising[i] = 100 + (i - 49) * 10
        prices = _make_prices(rising)
        signals = generate_signals(prices, 20, 50)
        # At least one BUY must appear in the second half
        assert "BUY" in signals.iloc[50:].values

    def test_sell_signal_on_death_cross(self):
        # Rise then fall
        prices = _rise_then_fall(100)
        signals = generate_signals(prices, 20, 50)
        assert "SELL" in signals.values

    def test_short_window_must_be_less_than_long(self):
        prices = _make_prices(list(range(1, 61)))
        with pytest.raises(ValueError):
            generate_signals(prices, 50, 20)

    def test_equal_windows_raise(self):
        prices = _make_prices(list(range(1, 61)))
        with pytest.raises(ValueError):
            generate_signals(prices, 20, 20)

    def test_valid_signal_values_only(self):
        prices = _rising_then_falling(120)
        signals = generate_signals(prices, 20, 50)
        assert set(signals.unique()).issubset({"BUY", "SELL", "HOLD"})


def _rise_then_fall(n: int) -> pd.Series:
    half = n // 2
    values = list(range(1, half + 1)) + list(range(half, 0, -1))
    return _make_prices(values[:n])


# ---------------------------------------------------------------------------
# latest_signal
# ---------------------------------------------------------------------------

class TestLatestSignal:
    def test_returns_string(self):
        prices = _make_prices(list(range(1, 61)))
        result = latest_signal(prices, 20, 50)
        assert isinstance(result, str)
        assert result in ("BUY", "SELL", "HOLD")

    def test_hold_on_flat_prices(self):
        prices = _make_prices([100.0] * 60)
        result = latest_signal(prices, 20, 50)
        assert result == "HOLD"
