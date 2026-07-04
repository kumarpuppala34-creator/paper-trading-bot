# Paper Trading Bot

Real live prices, fake money. Built from the fabrichhhhhh "Simulation Trading
Bot" guide. Trades crypto (bitcoin, ethereum, solana via CoinGecko) and
stocks (AAPL, MSFT, SPY via Yahoo Finance) long-only, spot-style.

## The one rule

Never fake a fill, a price, or a profit. Every trade uses a real live price,
real crypto trading fees (0.1% Binance spot taker, applied as a
representative real-exchange fee), $0 stock commission (standard for US
retail brokers), and a disclosed slippage estimate (since free data gives no
real order-book depth). Losses are recorded as losses.

## Run it

```
cd paper-trading-bot
source venv/bin/activate
python3 bot.py            # the live trading loop (Ctrl+C to stop)
streamlit run dashboard.py  # in a second terminal: the live dashboard
```

Open http://localhost:8501 for the dashboard.

## How it works

1. `data_feed.py` - real live/historical prices, no synthetic numbers.
2. `engine.py` - the honest portfolio: opens/closes positions with real fees + slippage.
3. `strategies.py` + `backtester.py` - SMA crossover, RSI mean-reversion, and
   momentum, each backtested on real recent history. Only strategies that
      clear a Sharpe/trade-count bar on real data are allowed to trade live.
      4. `kelly.py` - fractional Kelly position sizing from each strategy's own
         real backtest win rate/payoff, capped at 25% of equity per trade.
         5. `risk.py` - if equity falls to 50% of its peak, the bot force-closes
            everything, logs the honest lesson (what was open, what the drawdown
               was), and resets the fake balance to $10,000. Nothing is deleted from
                  the trade history.
                  6. `dashboard.py` - read-only Streamlit view of equity, positions, trades,
                     strategy scores, and reset history.

                     ## Known limitations (disclosed, not hidden)

                     - CoinGecko's free tier is rate-limited; the bot retries with backoff and
                       caches prices briefly (15-60s) to stay under it.
                       - Crypto backtests use ~89 days of hourly closes (CoinGecko's free
                         granularity cutoff); stock backtests use up to 730 days of hourly bars
                           from Yahoo Finance.
                           - Slippage is a disclosed modeling estimate, not measured from a real order
                             book, because free data doesn't expose one.
                             - No shorting or futures/funding - this is spot-only, matching the honest
                               fee model.

                               This is a simulation. It has no edge beyond what the backtester actually
                               measures on real history, it will lose trades, and it can blow through its
                               whole fake balance - that's why the reset-and-learn loop exists.
                               
