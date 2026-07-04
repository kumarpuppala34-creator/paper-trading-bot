"""
Central config. Every number here that affects money has a comment naming
the real-world source it came from, per the "never fake a number" rule.
"""

STARTING_BALANCE = 10_000.00

# Crypto: CoinGecko public REST API, no key required, no geo-blocking.
# (api.binance.com returns HTTP 451 - legally blocked - for US-based
# requests, so we use CoinGecko's free aggregated market-price API instead:
# https://www.coingecko.com/en/api/documentation)
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
CRYPTO_SYMBOLS = ["bitcoin", "ethereum", "solana"]
CRYPTO_DISPLAY = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}

# CoinGecko gives us an aggregated market price, not a single exchange fill,
# so there is no single "real" fee tied to that price. We charge Binance's
# public spot taker fee schedule as a disclosed, representative real-exchange
# fee (https://www.binance.com/en/fee/spotMaker, checked 2026-07): 0.1% per side.
CRYPTO_TAKER_FEE_RATE = 0.001

# Stocks: Yahoo Finance via yfinance, free, no key, ~15min-delayed quotes
# (yfinance itself documents its data as Yahoo Finance's public, unauthenticated
# endpoints - https://github.com/ranaroussi/yfinance). We are honest about the
# delay in the dashboard rather than pretending it's real-time.
STOCK_SYMBOLS = ["AAPL", "MSFT", "SPY"]

# Most US retail brokers (Fidelity, Schwab, Robinhood) charge $0 commission on
# stock trades since 2019. We charge $0 explicitly rather than inventing a fee.
STOCK_COMMISSION = 0.0

# Slippage: free data sources give us no real order-book depth, so we cannot
# pull a "real" slippage number the way we can a real fee. We model it
# honestly as a small, disclosed estimate rather than hiding it or pretending
# it's zero. This is a modeling assumption, not a verified market fact.
CRYPTO_SLIPPAGE_BPS = 5     # 0.05%, applied against the trader on every fill
STOCK_SLIPPAGE_BPS = 2      # 0.02%

# Perpetual futures funding rates only apply to perpetual futures contracts,
# not to the spot positions this bot trades. We do not simulate funding
# because we are not trading a perpetual product - saying so beats faking a
# funding number for a product we don't hold.
FUNDING_APPLIES = False

# Position sizing
KELLY_FRACTION = 0.5          # "fractional Kelly" - half of full Kelly, standard practice
MAX_POSITION_FRACTION = 0.25  # never bet more than 25% of equity on one trade, no matter what Kelly says
MIN_TRADE_HISTORY_FOR_KELLY = 20  # need at least this many closed trades before trusting a win-rate

# Reset-and-learn
MAX_DRAWDOWN_BEFORE_RESET = 0.5   # if equity falls to 50% of its peak, stop and reset
RESET_STARTING_BALANCE = STARTING_BALANCE

# Backtesting
# 89 days keeps CoinGecko's free crypto history hourly rather than daily
# (see data_feed._coingecko_ohlc) so every strategy gets enough real trades
# to be judged fairly.
BACKTEST_LOOKBACK_DAYS = 89
MIN_SHARPE_TO_PASS = 0.3     # strategies scoring below this on real history are rejected
MIN_TRADES_TO_JUDGE = 10     # too few trades to say anything honest about a strategy

# Live loop
POLL_INTERVAL_SECONDS = 30

DB_PATH = "trading_bot.db"
