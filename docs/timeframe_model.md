# Two-Timeframe Prediction Model

Praecursor-EGX now separates opportunity analysis into two timeframes.

## 1. Next-Day Candidates

Goal:

```text
Find stocks most likely to move in the following trading session.
```

This model emphasizes:

```text
closing breakouts
volume-confirmed breakouts
MACD acceleration
relative volume
not being too overextended
```

Typical labels:

```text
Next-Day Breakout Candidate
Next-Day Breakout Candidate - Extended
High-Priority Next-Day Watch
Watchlist Tomorrow
Avoid Tomorrow
```

## 2. Swing Candidates

Goal:

```text
Find stocks with 10-20 bar continuation or recovery potential.
```

This model emphasizes:

```text
trend continuation
RSI recovery
MACD histogram improvement
EMA20 reclaim
volume spike from weakness
reversal momentum
```

Typical labels:

```text
Swing Trend Continuation
Swing Reversal Watch
Swing Recovery Watch
Swing Watchlist
Avoid Swing
```

## Why separate them?

Backtesting showed that some labels were poor next-day signals but strong 20-bar signals. In particular, early reversal setups often need time to develop.

A stock can therefore be:

```text
Avoid Tomorrow
but
Swing Reversal Watch
```

This is not a contradiction. It means the setup is not ready for the next session but may be worth monitoring over a longer horizon.
