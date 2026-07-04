"""
  Real price data. No synthetic numbers anywhere in this file.

  Crypto -> CoinGecko public REST API (api.coingecko.com/api/v3), no key needed.
  Stocks -> Yahoo Finance via yfinance, free, no key, quotes may run ~15min delayed.
    """
    from __future__ import annotations

    import time
    import requests
    import pandas as pd

    import config


    def is_crypto(symbol: str) -> bool:
    return symbol in config.CRYPTO_SYMBOLS


      def _get_with_retry(url: str, params: dict, timeout: float, retries: int = 6) -> requests.Response:
          """CoinGecko's free tier rate-limits aggressively; back off and retry on 429 instead of failing the cycle."""
          delay = 3.0
          for attempt in range(retries):
              r = requests.get(url, params=params, timeout=timeout)
              if r.status_code != 429:
                  r.raise_for_status()
                  return r
              if attempt == retries - 1:
                  r.raise_for_status()
              time.sleep(delay)
              delay *= 2
          raise RuntimeError("unreachable")


      _price_cache: dict[str, tuple[float, float]] = {}
_PRICE_CACHE_TTL_SECONDS = 15


  def get_live_price(symbol: str) -> float:
    """
          Return the current real price for one symbol, cached briefly in-process
          so multiple strategies checking the same symbol in one trading cycle
          don't each re-hit the free API and trip its rate limit.
          """
          cached = _price_cache.get(symbol)
          if cached and (time.time() - cached[0]) < _PRICE_CACHE_TTL_SECONDS:
              return cached[1]
          price = _coingecko_prices([symbol])[symbol] if is_crypto(symbol) else _yahoo_price(symbol)
          _price_cache[symbol] = (time.time(), price)
          return price


      def get_live_prices(symbols: list[str]) -> dict[str, float]:
          crypto = [s for s in symbols if is_crypto(s)]
          stocks = [s for s in symbols if not is_crypto(s)]
          out: dict[str, float] = {}
    if crypto:
        out.update(_coingecko_prices(crypto))
              for s in stocks:
                  out[s] = _yahoo_price(s)
              return out


          def _coingecko_prices(ids: list[str]) -> dict[str, float]:
              r = _get_with_retry(
                  f"{config.COINGECKO_BASE_URL}/simple/price",
                  params={"ids": ",".join(ids), "vs_currencies": "usd"},
                  timeout=10,
              )
              data = r.json()
              missing = [i for i in ids if i not in data]
              if missing:
                  raise RuntimeError(f"CoinGecko did not return prices for: {missing}")
              return {i: float(data[i]["usd"]) for i in ids}


def _yahoo_price(symbol: str) -> float:
    import yfinance as yf

          ticker = yf.Ticker(symbol)
          fast = ticker.fast_info
          price = fast.get("lastPrice") if hasattr(fast, "get") else fast["lastPrice"]
          if price is None:
              raise RuntimeError(f"Yahoo Finance returned no price for {symbol}")
          return float(price)


      _history_cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
_HISTORY_CACHE_TTL_SECONDS = 60


  def get_historical(symbol: str, days: int) -> pd.DataFrame:
    """
          Real history, cached in-process for a short time. This is purely to
                avoid hammering CoinGecko's free rate limit with duplicate requests for
                the same symbol within one trading cycle - it never changes the prices
                themselves, only how often we re-fetch them.
                """
                key = (symbol, days)
                cached = _history_cache.get(key)
                if cached and (time.time() - cached[0]) < _HISTORY_CACHE_TTL_SECONDS:
                    return cached[1].copy()

                df = _coingecko_ohlc(symbol, days) if is_crypto(symbol) else _yahoo_history(symbol, days)
                _history_cache[key] = (time.time(), df)
                return df.copy()


            def _coingecko_ohlc(symbol: str, days: int) -> pd.DataFrame:
                """
                CoinGecko's free market_chart endpoint auto-picks granularity by the
                `days` window: hourly under 90 days, daily at 90+. We cap the request at
                89 days to keep hourly bars - enough real data points to honestly judge
                a strategy - rather than asking for a longer window and getting sparse
                4-day-apart closes that would starve every strategy of trades.
                This gives real closing prices only (no separate intrabar high/low from
                                                         this endpoint), so we set open == high == low == close: a real price,
    just without invented intrabar detail.
          """
          capped_days = min(days, 89)
          r = _get_with_retry(
              f"{config.COINGECKO_BASE_URL}/coins/{symbol}/market_chart",
              params={"vs_currency": "usd", "days": capped_days},
              timeout=15,
          )
          prices = r.json().get("prices", [])
          if not prices:
              raise RuntimeError(f"CoinGecko returned no price history for {symbol}")
          df = pd.DataFrame(prices, columns=["open_time", "close"])
          df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
          df["open"] = df["close"]
          df["high"] = df["close"]
          df["low"] = df["close"]
          df["volume"] = 0.0
          return df[["open_time", "open", "high", "low", "close", "volume"]]


      def _yahoo_history(symbol: str, days: int) -> pd.DataFrame:
    import yfinance as yf

          period = f"{max(days, 1)}d"
          # Yahoo serves 1h bars up to 730 days back; use hourly for real trade
                # density in the backtest instead of falling back to sparse daily bars.
                interval = "1h" if days <= 730 else "1d"
                df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
                if df.empty:
                    raise RuntimeError(f"Yahoo Finance returned no history for {symbol}")
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.reset_index()
                time_col = "Datetime" if "Datetime" in df.columns else "Date"
                df = df.rename(columns={
                          time_col: "open_time", "Open": "open", "High": "high",
                          "Low": "low", "Close": "close", "Volume": "volume",
                })
                return df[["open_time", "open", "high", "low", "close", "volume"]]


            if __name__ == "__main__":
                prices = get_live_prices(config.CRYPTO_SYMBOLS + config.STOCK_SYMBOLS)
                for sym, px in prices.items():
                    print(f"{sym}: {px}")
                time.sleep(0)
            
