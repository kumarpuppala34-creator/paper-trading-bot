"""
The live paper-trading loop. Ties together the honest engine, the
backtest-approved strategies, Kelly sizing, and the reset-and-learn loop.

Run: python bot.py
Stop any time with Ctrl+C - state is persisted to trading_bot.db after
every action, so the dashboard (dashboard.py) can read it independently and
a restart picks up where it left off.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

import pandas as pd

import config
import data_feed
import db
import engine
import kelly
import risk
import strategies


def load_cash() -> float:
    val = db.get_state("cash")
    return float(val) if val is not None else config.STARTING_BALANCE


def save_cash(cash: float):
    db.set_state("cash", str(cash))


def approved_strategies() -> dict[str, list[str]]:
    """symbol -> list of strategy names that passed the last backtest."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT symbol, strategy FROM strategy_scores WHERE passed = 1"
        ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["symbol"], []).append(r["strategy"])
    return out


def strategy_stats(strategy: str, symbol: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM strategy_scores WHERE strategy = ? AND symbol = ?",
            (strategy, symbol),
        ).fetchone()
    return dict(row) if row else None


def live_signal(symbol: str, strategy_name: str, live_price: float | None = None) -> bool:
    """True if the strategy says 'be long' right now, using real recent history + the live price."""
    history = data_feed.get_historical(symbol, config.BACKTEST_LOOKBACK_DAYS)
    if live_price is None:
        live_price = data_feed.get_live_price(symbol)
    now_row = pd.DataFrame([{
        "open_time": pd.Timestamp.now(tz="UTC").tz_localize(None),
        "open": live_price, "high": live_price, "low": live_price,
        "close": live_price, "volume": 0.0,
    }])
    df = pd.concat([history, now_row], ignore_index=True)
    position = strategies.STRATEGIES[strategy_name](df)
    return bool(position.iloc[-1] == 1)


def run_once(portfolio: engine.Portfolio, approved: dict[str, list[str]]):
    positions = portfolio.load_positions()

    all_symbols = sorted(set(approved.keys()) | set(positions.keys()))
    live_prices = data_feed.get_live_prices(all_symbols) if all_symbols else {}

    # 1. exit check: close anything whose approved strategy now says "flat"
    for symbol, position in list(positions.items()):
        strategy_name = position.strategy
        if strategy_name not in approved.get(symbol, []):
            # this strategy/symbol pair no longer passes backtesting - exit honestly rather than keep riding it
            pnl = portfolio.close_position(position, reason="strategy_no_longer_approved")
            del positions[symbol]
            continue
        if not live_signal(symbol, strategy_name, live_price=live_prices.get(symbol)):
            pnl = portfolio.close_position(position, reason="strategy_signal_exit")
            del positions[symbol]

    # 2. entry check: for approved symbols with no open position, size with Kelly and open
    equity_now = portfolio.mark_to_market(positions)
    for symbol, strategy_names in approved.items():
        if symbol in positions:
            continue
        for strategy_name in strategy_names:
            stats = strategy_stats(strategy_name, symbol)
            if not stats:
                continue
            if not live_signal(symbol, strategy_name, live_price=live_prices.get(symbol)):
                continue
            notional = kelly.position_size_usd(
                equity_now, stats["win_rate"], stats["avg_win"], stats["avg_loss"], stats["num_trades"],
            )
            if notional < 10:  # too small to bother with fake $ fees swallowing it
                continue
            notional = min(notional, portfolio.cash * 0.95)
            if notional < 10:
                continue
            try:
                portfolio.open_position(symbol, notional, strategy=strategy_name)
                positions = portfolio.load_positions()
            except ValueError as e:
                db.log_event("warn", str(e))
            break  # one approved strategy per symbol at a time

    # 3. mark to market, record equity, check drawdown
    positions = portfolio.load_positions()
    equity = portfolio.mark_to_market(positions)
    with db.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO equity_curve (ts, equity, cash) VALUES (?, ?, ?)",
            (time.time(), equity, portfolio.cash),
        )
    save_cash(portfolio.cash)

    reset = risk.check_and_reset(portfolio, positions, equity)
    if reset:
        save_cash(portfolio.cash)

    return equity


def main():
    db.init_db()
    print("Running the backtest to decide which strategies are allowed to trade live...")
    import backtester
    try:
        backtester.run_all()
    except Exception as e:
        # a bad backtest run must not kill the whole bot before it even starts
        # trading - log it honestly and carry on with whatever did get scored.
        db.log_event("error", f"Initial backtest run failed: {e}")

    approved = approved_strategies()
    if not approved:
        print("No strategy passed the backtest on any symbol - honestly, nothing is approved to trade live yet.")
    else:
        for symbol, names in approved.items():
            print(f"  approved: {symbol} -> {names}")

    portfolio = engine.Portfolio(starting_balance=load_cash())
    db.log_event("info", f"Bot started. Cash=${portfolio.cash:,.2f}. Approved: {approved}")

    once = "--once" in sys.argv
    while True:
        try:
            equity = run_once(portfolio, approved)
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            print(f"[{ts}] equity=${equity:,.2f} cash=${portfolio.cash:,.2f}")
        except Exception as e:
            db.log_event("error", f"run_once failed: {e}")
            print(f"error this cycle: {e}", file=sys.stderr)

        if once:
            break

        # re-run the backtest periodically so "approved" stays current with real data
        if int(time.time()) % 3600 < config.POLL_INTERVAL_SECONDS:
            try:
                backtester.run_all()
                approved = approved_strategies()
            except Exception as e:
                db.log_event("error", f"Periodic backtest run failed: {e}")

        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
