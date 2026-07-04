"""
Live dashboard. Displays what the bot has done, straight from trading_bot.db.

Local use: run bot.py separately, then `streamlit run dashboard.py`.
Cloud use (e.g. Streamlit Community Cloud): there's no separate always-on
process available, so this file starts the trading loop itself as a
background thread the first time the app process boots (see
start_bot_background below) - one instance per app process, not per viewer.
"""
from __future__ import annotations

import threading

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import bot as bot_module
import config
import db

st.set_page_config(page_title="Paper Trading Bot", layout="wide")
st_autorefresh(interval=config.POLL_INTERVAL_SECONDS * 1000, key="refresh")


@st.cache_resource
def start_bot_background():
      """
          Runs once per app process (st.cache_resource is shared across all
              viewers, unlike st.session_state which is per-browser-session) - so
                  opening the dashboard from ten browsers doesn't start ten trading bots.
                      """
      thread = threading.Thread(target=bot_module.main, daemon=True)
      thread.start()
      return thread


start_bot_background()

st.title("Paper Trading Bot - live, honest, fake money")
st.caption(
      "Real live prices, simulated fake balance. Real fees and disclosed slippage are charged on "
      "every trade. This is a simulation - it can and will lose money."
)

try:
      db.init_db()
except Exception as e:
      st.error(f"Could not open the database: {e}")
      st.stop()

with db.connect() as conn:
      equity_rows = conn.execute("SELECT * FROM equity_curve ORDER BY ts ASC").fetchall()
      position_rows = conn.execute("SELECT * FROM positions").fetchall()
      trade_rows = conn.execute("SELECT * FROM trades ORDER BY closed_at DESC LIMIT 100").fetchall()
      score_rows = conn.execute("SELECT * FROM strategy_scores ORDER BY passed DESC, sharpe DESC").fetchall()
      reset_rows = conn.execute("SELECT * FROM resets ORDER BY ts DESC").fetchall()
      event_rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50").fetchall()

cash = float(db.get_state("cash", config.STARTING_BALANCE))
equity = equity_rows[-1]["equity"] if equity_rows else config.STARTING_BALANCE
peak = float(db.get_state("peak_equity", config.STARTING_BALANCE))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Equity (fake $)", f"${equity:,.2f}", f"{equity - config.STARTING_BALANCE:+,.2f}")
col2.metric("Cash (fake $)", f"${cash:,.2f}")
col3.metric("Peak equity", f"${peak:,.2f}")
col4.metric("Drawdown from peak", f"{(1 - equity / peak) * 100:.1f}%" if peak > 0 else "0%")

st.subheader("Equity curve")
if equity_rows:
      df = pd.DataFrame([dict(r) for r in equity_rows])
      df["time"] = pd.to_datetime(df["ts"], unit="s")
      st.line_chart(df.set_index("time")[["equity", "cash"]])
else:
      st.info("No equity history yet - start bot.py to begin trading.")

st.subheader("Open positions")
if position_rows:
      df = pd.DataFrame([dict(r) for r in position_rows])
      st.dataframe(df, use_container_width=True, hide_index=True)
else:
      st.write("No open positions.")

st.subheader("Strategy backtest scores (only PASS strategies trade live)")
if score_rows:
      df = pd.DataFrame([dict(r) for r in score_rows])
      df["passed"] = df["passed"].map({1: "PASS", 0: "FAIL"})
      st.dataframe(df, use_container_width=True, hide_index=True)
else:
      st.write("No backtest results yet.")

st.subheader("Recent closed trades")
if trade_rows:
      df = pd.DataFrame([dict(r) for r in trade_rows])
      df["closed_at"] = pd.to_datetime(df["closed_at"], unit="s")
      df["result"] = df["pnl"].apply(lambda x: "WIN" if x >= 0 else "LOSS")
      st.dataframe(df, use_container_width=True, hide_index=True)
else:
      st.write("No closed trades yet.")

st.subheader("Reset-and-learn history")
if reset_rows:
      for r in reset_rows:
                st.warning(dict(r)["lesson"])
else:
      st.write("No resets yet - the bot hasn't blown up its fake balance (yet).")

with st.expander("Raw event log"):
      for r in event_rows:
                e = dict(r)
                st.text(f"[{e['level']}] {e['message']}")
        
