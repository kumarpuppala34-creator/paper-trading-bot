"""SQLite persistence shared by the live engine and the dashboard."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
        value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
                side TEXT NOT NULL,
                    qty REAL NOT NULL,
                        entry_price REAL NOT NULL,
                            cost_basis REAL NOT NULL,
                                strategy TEXT NOT NULL,
                                    opened_at REAL NOT NULL
                                    );

                                    CREATE TABLE IF NOT EXISTS trades (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            symbol TEXT NOT NULL,
                                                side TEXT NOT NULL,
                                                    qty REAL NOT NULL,
                                                        entry_price REAL NOT NULL,
                                                            exit_price REAL NOT NULL,
                                                                fee_paid REAL NOT NULL,
                                                                    slippage_cost REAL NOT NULL,
                                                                        pnl REAL NOT NULL,
                                                                            strategy TEXT NOT NULL,
                                                                                opened_at REAL NOT NULL,
                                                                                    closed_at REAL NOT NULL,
                                                                                        close_reason TEXT NOT NULL
                                                                                        );

                                                                                        CREATE TABLE IF NOT EXISTS equity_curve (
                                                                                            ts REAL PRIMARY KEY,
                                                                                                equity REAL NOT NULL,
                                                                                                    cash REAL NOT NULL
                                                                                                    );
                                                                                                    
                                                                                                    CREATE TABLE IF NOT EXISTS strategy_scores (
                                                                                                        strategy TEXT NOT NULL,
                                                                                                            symbol TEXT NOT NULL,
                                                                                                                passed INTEGER NOT NULL,
                                                                                                                    sharpe REAL NOT NULL,
                                                                                                                        win_rate REAL NOT NULL,
                                                                                                                            avg_win REAL NOT NULL,
                                                                                                                                avg_loss REAL NOT NULL,
                                                                                                                                    num_trades INTEGER NOT NULL,
                                                                                                                                        scored_at REAL NOT NULL,
                                                                                                                                            PRIMARY KEY (strategy, symbol)
                                                                                                                                            );
                                                                                                                                            
                                                                                                                                            CREATE TABLE IF NOT EXISTS resets (
                                                                                                                                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                                                                                                    ts REAL NOT NULL,
                                                                                                                                                        peak_equity REAL NOT NULL,
                                                                                                                                                            equity_at_reset REAL NOT NULL,
                                                                                                                                                                drawdown_pct REAL NOT NULL,
                                                                                                                                                                    lesson TEXT NOT NULL
                                                                                                                                                                    );
                                                                                                                                                                    
                                                                                                                                                                    CREATE TABLE IF NOT EXISTS events (
                                                                                                                                                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                                                                                                                            ts REAL NOT NULL,
                                                                                                                                                                                level TEXT NOT NULL,
                                                                                                                                                                                    message TEXT NOT NULL
                                                                                                                                                                                    );
                                                                                                                                                                                    """


@contextmanager
def connect():
      conn = sqlite3.connect(config.DB_PATH, timeout=30)
      conn.row_factory = sqlite3.Row
      try:
                yield conn
                conn.commit()
finally:
        conn.close()


def init_db():
      with connect() as conn:
                conn.executescript(SCHEMA)


def log_event(level: str, message: str):
      with connect() as conn:
                conn.execute(
                              "INSERT INTO events (ts, level, message) VALUES (?, ?, ?)",
                              (time.time(), level, message),
                )


def get_state(key: str, default=None):
      with connect() as conn:
                row = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
                return row["value"] if row else default


def set_state(key: str, value: str):
      with connect() as conn:
                conn.execute(
                              "INSERT INTO bot_state (key, value) VALUES (?, ?) "
                              "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                              (key, value),
                )


if __name__ == "__main__":
      init_db()
      print(f"Initialized {config.DB_PATH}")
  
