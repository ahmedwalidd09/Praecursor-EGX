# Praecursor-EGX Scoring Model

Praecursor-EGX uses a transparent technical score. It is not a guarantee of future returns; it is a ranking heuristic to identify stocks that deserve further review.

## Current score: 100 points

| Category | Max Points | Purpose |
| --- | ---: | --- |
| Trend | 45 | Prefer stocks in a short/medium/long-term uptrend. |
| Momentum | 35 | Prefer healthy bullish momentum without excessive overextension. |
| Volume confirmation | 20 | Prefer moves supported by above-average volume. |

## Trend: 45 points

| Rule | Points |
| --- | ---: |
| Latest close > EMA20 | 15 |
| EMA20 > EMA50 | 15 |
| EMA50 > EMA200 | 15 |

## Momentum: 35 points

Based on RSI14:

| RSI14 Range | Points | Meaning |
| --- | ---: | --- |
| 50 to 70 | 35 | Healthy bullish momentum |
| >70 to 75 | 22 | Strong but becoming extended |
| >75 | 8 | Overextended; pullback risk is higher |
| 40 to <50 | 10 | Neutral to slightly weak |
| <40 | 0 | Weak momentum |

## Volume confirmation: 20 points

Based on Relative Volume 20:

```text
Relative Volume 20 = latest volume / average volume of previous 20 bars
```

| Relative Volume 20 | Points | Meaning |
| --- | ---: | --- |
| >= 1.50 | 20 | Strong volume confirmation |
| >= 1.00 and < 1.50 | 15 | Supportive volume |
| >= 0.75 and < 1.00 | 8 | Slightly weak volume |
| < 0.75 | 0 | Weak volume confirmation |

## Why volume was added before ATR/breakout

Current public sources show many high/low normalization warnings. EMA, RSI, and volume-based metrics depend mostly on close and volume fields, which are currently more reliable than high/low fields.

ATR, breakout detection, and candlestick patterns should be added after improving high/low confidence through more source validation.
