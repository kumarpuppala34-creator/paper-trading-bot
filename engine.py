"""
The honest engine. Fake money, real prices, real fees, disclosed slippage.

The one rule: never fake a fill, a price, or a profit. Every close uses the
live price fetched at close time, fees are always subtracted, and a losing
trade is recorded as a loss - it is never rounded away.

Positions are long-only spot (buy, later sell). We do not simulate shorting
or margin, because that would need borrowing mechanics and a funding rate we
already decided not to fake (see config.FUNDING_APPLIES) - this bot only
holds what it can actually pay fake cash for, like a real spot account.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import config
import data_feed
import db


def fee_rate_for(symbol: str) -> float:
    return config.CRYPTO_TAKER_FEE_RATE if data_feed.is_crypto(symbol) else 0.0


def commission_for(symbol: str) -> float:
    return 0.0 if data_feed.is_crypto(symbol) else config.STOCK_COMMISSION


def slippage_bps_for(symbol: str) -> float:
    return config.CRYPTO_SLIPPAGE_BPS if data_feed.is_crypto(symbol) else config.STOCK_SLIPPAGE_BPS


@dataclass
class Position:
    symbol: str
    qty: float
    entry_price: float   # the real fill price, after slippage
    cost_basis: float     # total fake cash spent, including fee
    strategy: str
    opened_at: float


class Portfolio:
    """Fake balance, tracked honestly against real prices."""

    def __init__(self, starting_balance: float = config.STARTING_BALANCE):
        self.cash = starting_balance

    def load_positions(self) -> dict[str, Position]:
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM positions").fetchall()
        return {
            r["symbol"]: Position(
                symbol=r["symbol"], qty=r["qty"], entry_price=r["entry_price"],
                cost_basis=r["cost_basis"], strategy=r["strategy"], opened_at=r["opened_at"],
            )
            for r in rows
        }

    def open_position(self, symbol: str, notional_usd: float, strategy: str) -> Position:
        """Buy with fake money at a real, slippage-adjusted price."""
        raw_price = data_feed.get_live_price(symbol)
        fill_price = _apply_slippage(raw_price, symbol, buying=True)

        fee = notional_usd * fee_rate_for(symbol) + commission_for(symbol)
        total_cost = notional_usd + fee
        if total_cost > self.cash:
            raise ValueError(
                f"Cannot open {symbol}: needs ${total_cost:.2f} fake cash, have ${self.cash:.2f}"
            )

        qty = notional_usd / fill_price
        self.cash -= total_cost
        opened_at = time.time()

        with db.connect() as conn:
            conn.execute(
                "INSERT INTO positions (symbol, side, qty, entry_price, cost_basis, strategy, opened_at) "
                "VALUES (?, 'long', ?, ?, ?, ?, ?)",
                (symbol, qty, fill_price, total_cost, strategy, opened_at),
            )
        db.log_event(
            "trade",
            f"OPEN long {symbol} qty={qty:.6f} @ ${fill_price:.4f} "
            f"(raw ${raw_price:.4f}) fee=${fee:.2f} strategy={strategy}",
        )
        return Position(symbol, qty, fill_price, total_cost, strategy, opened_at)

    def close_position(self, position: Position, reason: str) -> float:
        """Sell truthfully at the current real price. Losses are never hidden."""
        raw_price = data_feed.get_live_price(position.symbol)
        fill_price = _apply_slippage(raw_price, position.symbol, buying=False)

        gross = position.qty * fill_price
        fee = gross * fee_rate_for(position.symbol) + commission_for(position.symbol)
        proceeds = gross - fee
        pnl = proceeds - position.cost_basis
        self.cash += proceeds

        with db.connect() as conn:
            conn.execute("DELETE FROM positions WHERE symbol = ?", (position.symbol,))
            conn.execute(
                "INSERT INTO trades (symbol, side, qty, entry_price, exit_price, fee_paid, "
                "slippage_cost, pnl, strategy, opened_at, closed_at, close_reason) "
                "VALUES (?,'long',?,?,?,?,?,?,?,?,?,?)",
                (
                    position.symbol, position.qty, position.entry_price,
                    fill_price, fee, abs(raw_price - fill_price) * position.qty, pnl,
                    position.strategy, position.opened_at, time.time(), reason,
                ),
            )
        outcome = "WIN" if pnl >= 0 else "LOSS"
        db.log_event(
            "trade",
            f"CLOSE long {position.symbol} @ ${fill_price:.4f} "
            f"(raw ${raw_price:.4f}) pnl=${pnl:.2f} [{outcome}] reason={reason}",
        )
        return pnl

    def mark_to_market(self, positions: dict[str, Position]) -> float:
        """Real equity right now: fake cash + positions valued at live prices."""
        equity = self.cash
        if not positions:
            return equity
        prices = data_feed.get_live_prices(list(positions.keys()))
        for symbol, pos in positions.items():
            equity += pos.qty * prices[symbol]
        return equity


def _apply_slippage(price: float, symbol: str, buying: bool) -> float:
    """
    Slippage always moves the fill against the trader - never in their favor.
    This is a disclosed modeling assumption (see config.py), not a verified
    market fact, because free data sources give us no real order-book depth.
    """
    factor = slippage_bps_for(symbol) / 10_000
    return price * (1 + factor) if buying else price * (1 - factor)


if __name__ == "__main__":
    db.init_db()
    p = Portfolio()
    pos = p.open_position("bitcoin", 100.0, strategy="manual_test")
    print("cash after open:", p.cash)
    pnl = p.close_position(pos, reason="manual_test_close")
    print("pnl:", pnl, "cash after close:", p.cash)
