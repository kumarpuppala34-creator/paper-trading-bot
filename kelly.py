"""
Fractional Kelly position sizing, sized from each strategy's own real
backtest stats - never a hand-picked or hallucinated number.

Formula (verified against the standard Kelly criterion, John L. Kelly Jr.,
1956): f* = (b*p - q) / b
  p = probability of a winning trade (from the backtest's real win rate)
  q = 1 - p
  b = payoff ratio = average win / average loss (from the same backtest)

Full Kelly is known to produce large, painful drawdowns even when the edge
is real, so we size at a fraction of it (config.KELLY_FRACTION) and cap the
single-trade risk regardless of what the formula says (config.MAX_POSITION_FRACTION).
"""
from __future__ import annotations

import config


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Return the fraction of equity to risk on one trade. 0 if there's no real edge."""
    if avg_loss >= 0 or avg_win <= 0:
        # avg_loss should be negative (it's a return); if it isn't, or there's
        # no positive average win, we cannot compute a meaningful payoff ratio.
        return 0.0

    p = win_rate
    q = 1 - p
    b = avg_win / abs(avg_loss)

    full_kelly = (b * p - q) / b
    if full_kelly <= 0:
        # the math says this strategy has no edge at this win rate/payoff -
        # honesty means sizing it at zero, not a token minimum bet.
        return 0.0

    sized = full_kelly * config.KELLY_FRACTION
    return min(sized, config.MAX_POSITION_FRACTION)


def position_size_usd(equity: float, win_rate: float, avg_win: float, avg_loss: float, num_trades: int) -> float:
    """Convert a Kelly fraction into a dollar amount, honestly refusing to size unproven strategies."""
    if num_trades < config.MIN_TRADE_HISTORY_FOR_KELLY:
        return 0.0
    frac = kelly_fraction(win_rate, avg_win, avg_loss)
    return equity * frac
