"""
The reset-and-learn loop. If the bot loses big, it stops, records the honest
lesson (what was open, what the drawdown was, at what equity), wipes its
fake balance back to the starting line, and starts over. Losing runs are
never hidden or deleted from the record - only the live balance resets.
"""
from __future__ import annotations

import time

import config
import db
import engine


def get_peak_equity() -> float:
    val = db.get_state("peak_equity")
    return float(val) if val is not None else config.STARTING_BALANCE


def update_peak_equity(current_equity: float) -> float:
    peak = max(get_peak_equity(), current_equity)
    db.set_state("peak_equity", str(peak))
    return peak


def check_and_reset(portfolio: engine.Portfolio, positions: dict[str, engine.Position], current_equity: float) -> bool:
    """
    Returns True if a reset happened. Call this every poll after marking to
    market - it decides on real, current equity vs. the real peak we've
    actually reached, never a hypothetical one.
    """
    peak = update_peak_equity(current_equity)
    if peak <= 0:
        return False

    drawdown = 1 - (current_equity / peak)
    if drawdown < config.MAX_DRAWDOWN_BEFORE_RESET:
        return False

    lesson = (
        f"Hit {drawdown:.0%} drawdown from peak ${peak:,.2f} down to ${current_equity:,.2f}. "
        f"Open positions at reset: "
        + (", ".join(f"{s} ({p.strategy})" for s, p in positions.items()) or "none")
        + ". This is recorded, not erased - the strategies/symbols above are what lost this run."
    )

    for symbol, position in list(positions.items()):
        pnl = portfolio.close_position(position, reason="reset_and_learn_forced_close")
        db.log_event("reset", f"Force-closed {symbol} at reset, pnl=${pnl:.2f}")

    with db.connect() as conn:
        conn.execute(
            "INSERT INTO resets (ts, peak_equity, equity_at_reset, drawdown_pct, lesson) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), peak, current_equity, drawdown, lesson),
        )

    portfolio.cash = config.RESET_STARTING_BALANCE
    db.set_state("peak_equity", str(config.RESET_STARTING_BALANCE))
    db.set_state("cash", str(config.RESET_STARTING_BALANCE))
    db.log_event("reset", f"RESET: balance restored to ${config.RESET_STARTING_BALANCE:,.2f}. {lesson}")
    return True
