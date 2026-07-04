"""
Simple, well-known strategies. Each takes a price history DataFrame (must
have a 'close' column, oldest row first) and returns a position series of
0 (flat) / 1 (long) for every row, using only information available up to
and including that row - no lookahead.

Formulas:
  - SMA crossover: simple moving average, textbook definition.
    - RSI: Wilder's Relative Strength Index (the original 1978 formula).
      - Momentum: raw N-period price return.
      These are standard, decades-old public formulas; we're not claiming any
      proprietary edge.
      """
      from __future__ import annotations

      import pandas as pd


      def sma_crossover(df: pd.DataFrame, fast: int = 10, slow: int = 50) -> pd.Series:
          fast_ma = df["close"].rolling(fast).mean()
              slow_ma = df["close"].rolling(slow).mean()
                  position = (fast_ma > slow_ma).astype(int)
                      return position.fillna(0)


                      def rsi(series: pd.Series, period: int = 14) -> pd.Series:
                          delta = series.diff()
                              gain = delta.clip(lower=0)
                                  loss = -delta.clip(upper=0)
                                      avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
                                          avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
                                              rs = avg_gain / avg_loss.replace(0, float("nan"))
                                                  return 100 - (100 / (1 + rs))


                                                  def rsi_mean_reversion(df: pd.DataFrame, period: int = 14, buy_below: float = 30, sell_above: float = 55) -> pd.Series:
                                                      r = rsi(df["close"], period)
                                                          position = pd.Series(0, index=df.index)
                                                              in_position = False
                                                                  for i in range(len(df)):
                                                                          if pd.isna(r.iloc[i]):
                                                                                      position.iloc[i] = 0
                                                                                                  continue
                                                                                                          if not in_position and r.iloc[i] < buy_below:
                                                                                                                      in_position = True
                                                                                                                              elif in_position and r.iloc[i] > sell_above:
                                                                                                                                          in_position = False
                                                                                                                                                  position.iloc[i] = int(in_position)
                                                                                                                                                      return position
                                                                                                                                                      
                                                                                                                                                      
                                                                                                                                                      def momentum(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
                                                                                                                                                          ret = df["close"].pct_change(lookback)
                                                                                                                                                              position = (ret > 0).astype(int)
                                                                                                                                                                  return position.fillna(0)
                                                                                                                                                                  
                                                                                                                                                                  
                                                                                                                                                                  STRATEGIES = {
                                                                                                                                                                      "sma_crossover": sma_crossover,
                                                                                                                                                                          "rsi_mean_reversion": rsi_mean_reversion,
                                                                                                                                                                              "momentum": momentum,
                                                                                                                                                                              }
                                                                                                                                                                              
