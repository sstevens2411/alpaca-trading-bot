"""Unit tests for risk.py — no network calls."""

import pytest

from src.risk import check_exposure, check_daily_loss, DailyRiskManager


# ---------------------------------------------------------------------------
# check_exposure
# ---------------------------------------------------------------------------

class TestCheckExposure:
    def test_allows_when_under_limit(self):
        positions = {"AAPL": 100.0, "MSFT": 150.0}  # total = 250
        ok, reason = check_exposure(positions, 100.0, max_exposure=500.0)
        assert ok is True
        assert reason == ""

    def test_blocks_when_over_limit(self):
        positions = {"AAPL": 400.0}  # total = 400
        ok, reason = check_exposure(positions, 150.0, max_exposure=500.0)
        assert ok is False
        assert "Exposure limit hit" in reason

    def test_exact_limit_is_allowed(self):
        positions = {"AAPL": 400.0}
        ok, _ = check_exposure(positions, 100.0, max_exposure=500.0)
        assert ok is True

    def test_one_cent_over_blocks(self):
        positions = {"AAPL": 400.0}
        ok, _ = check_exposure(positions, 100.01, max_exposure=500.0)
        assert ok is False

    def test_empty_positions(self):
        ok, _ = check_exposure({}, 100.0, max_exposure=500.0)
        assert ok is True

    def test_negative_market_value_uses_abs(self):
        # Short positions have negative market value; use abs for exposure
        positions = {"AAPL": -200.0}
        ok, _ = check_exposure(positions, 200.0, max_exposure=500.0)
        assert ok is True  # 200 + 200 = 400 < 500


# ---------------------------------------------------------------------------
# check_daily_loss
# ---------------------------------------------------------------------------

class TestCheckDailyLoss:
    def test_allows_when_no_loss(self):
        ok, reason = check_daily_loss(10_000.0, 10_050.0, max_daily_loss=25.0)
        assert ok is True
        assert reason == ""

    def test_allows_small_loss(self):
        ok, _ = check_daily_loss(10_000.0, 9_990.0, max_daily_loss=25.0)
        assert ok is True

    def test_blocks_at_exact_limit(self):
        ok, reason = check_daily_loss(10_000.0, 9_975.0, max_daily_loss=25.0)
        assert ok is False
        assert "Daily loss limit hit" in reason

    def test_blocks_beyond_limit(self):
        ok, _ = check_daily_loss(10_000.0, 9_950.0, max_daily_loss=25.0)
        assert ok is False

    def test_allows_zero_loss(self):
        ok, _ = check_daily_loss(10_000.0, 10_000.0, max_daily_loss=25.0)
        assert ok is True


# ---------------------------------------------------------------------------
# DailyRiskManager
# ---------------------------------------------------------------------------

class TestDailyRiskManager:
    def _make_rm(self, start_equity=10_000.0, max_loss=25.0, max_exposure=500.0):
        return DailyRiskManager(
            start_of_day_equity=start_equity,
            max_daily_loss=max_loss,
            max_total_exposure=max_exposure,
        )

    def test_allows_normal_trade(self):
        rm = self._make_rm()
        ok, reason = rm.can_trade({}, 100.0, current_equity=10_000.0)
        assert ok is True

    def test_halts_on_daily_loss(self):
        rm = self._make_rm(start_equity=10_000.0, max_loss=25.0)
        ok, reason = rm.can_trade({}, 100.0, current_equity=9_974.0)
        assert ok is False
        assert rm.is_halted is True

    def test_stays_halted_after_halt(self):
        rm = self._make_rm(start_equity=10_000.0, max_loss=25.0)
        rm.can_trade({}, 100.0, current_equity=9_974.0)  # triggers halt
        ok, reason = rm.can_trade({}, 100.0, current_equity=10_100.0)  # equity recovered
        assert ok is False  # still halted for the day

    def test_blocks_on_exposure_without_halt(self):
        rm = self._make_rm(max_exposure=500.0)
        positions = {"AAPL": 450.0}
        ok, reason = rm.can_trade(positions, 100.0, current_equity=10_000.0)
        assert ok is False
        # Exposure block should NOT trigger a halt
        assert rm.is_halted is False

    def test_exposure_block_allows_next_smaller_trade(self):
        rm = self._make_rm(max_exposure=500.0)
        positions = {"AAPL": 450.0}
        rm.can_trade(positions, 100.0, current_equity=10_000.0)  # blocked
        ok, _ = rm.can_trade(positions, 40.0, current_equity=10_000.0)  # 450+40=490 < 500
        assert ok is True

    def test_does_not_halt_on_exposure(self):
        rm = self._make_rm(max_exposure=500.0)
        positions = {"AAPL": 450.0}
        rm.can_trade(positions, 100.0, current_equity=10_000.0)
        assert rm.is_halted is False
