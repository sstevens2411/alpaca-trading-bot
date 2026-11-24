"""
Risk management — pure functions, no I/O.

Checks:
  1. Max total exposure: sum of all open position market values.
  2. Max daily loss: realized + unrealized P&L vs. start-of-day portfolio value.

Both functions return (allowed: bool, reason: str).
"""

from __future__ import annotations


def check_exposure(
    current_positions: dict[str, float],
    new_trade_amount: float,
    max_exposure: float,
) -> tuple[bool, str]:
    """
    Return (True, '') if adding *new_trade_amount* keeps total exposure
    within *max_exposure*, otherwise (False, reason).

    Parameters
    ----------
    current_positions : {symbol: market_value}
    new_trade_amount  : dollar amount of the proposed new position
    max_exposure      : maximum allowed total exposure in dollars
    """
    current_total = sum(abs(v) for v in current_positions.values())
    projected = current_total + abs(new_trade_amount)
    if projected > max_exposure:
        reason = (
            f"Exposure limit hit: current ${current_total:.2f} + "
            f"new ${new_trade_amount:.2f} = ${projected:.2f} "
            f"> max ${max_exposure:.2f}"
        )
        return False, reason
    return True, ""


def check_daily_loss(
    start_of_day_equity: float,
    current_equity: float,
    max_daily_loss: float,
) -> tuple[bool, str]:
    """
    Return (True, '') if the day's loss is still within *max_daily_loss*,
    otherwise (False, reason).

    Parameters
    ----------
    start_of_day_equity : portfolio equity at market open
    current_equity      : current portfolio equity
    max_daily_loss      : maximum allowed loss for the day (positive number)
    """
    daily_loss = start_of_day_equity - current_equity
    if daily_loss >= max_daily_loss:
        reason = (
            f"Daily loss limit hit: lost ${daily_loss:.2f} "
            f">= max ${max_daily_loss:.2f}. "
            "Halting trading for the rest of the day."
        )
        return False, reason
    return True, ""


class DailyRiskManager:
    """
    Stateful wrapper used by the live bot to track risk across a session.

    Usage
    -----
    rm = DailyRiskManager(start_equity=10_000, cfg=config["risk"])
    allowed, reason = rm.can_trade(positions, trade_amount, current_equity)
    if not allowed:
        # log reason, skip order
    """

    def __init__(self, start_of_day_equity: float, max_daily_loss: float, max_total_exposure: float):
        self.start_of_day_equity = start_of_day_equity
        self.max_daily_loss = max_daily_loss
        self.max_total_exposure = max_total_exposure
        self._halted = False
        self._halt_reason = ""

    @property
    def is_halted(self) -> bool:
        return self._halted

    def can_trade(
        self,
        current_positions: dict[str, float],
        new_trade_amount: float,
        current_equity: float,
    ) -> tuple[bool, str]:
        """Return (allowed, reason). Once halted, always returns False."""
        if self._halted:
            return False, self._halt_reason

        loss_ok, loss_reason = check_daily_loss(
            self.start_of_day_equity, current_equity, self.max_daily_loss
        )
        if not loss_ok:
            self._halted = True
            self._halt_reason = loss_reason
            return False, loss_reason

        exp_ok, exp_reason = check_exposure(
            current_positions, new_trade_amount, self.max_total_exposure
        )
        if not exp_ok:
            return False, exp_reason

        return True, ""
