# Praecursor-EGX Scoring Model

Praecursor-EGX uses a transparent technical score. It is not a guarantee of future returns; it is a ranking heuristic to identify stocks that deserve further review.

## Current score: 100 points

| Category | Max Points | Purpose |
| --- | ---: | --- |
| Trend structure | 30 | Prefer stocks in a short/medium/long-term uptrend. |
| RSI momentum | 25 | Prefer healthy bullish momentum without excessive overextension. |
| MACD confirmation | 15 | Prefer positive MACD momentum and acceleration. |
| 20-bar price momentum | 15 | Prefer stocks with positive recent price performance. |
| Volume confirmation | 15 | Prefer moves supported by above-average volume. |

## Trend structure: 30 points

| Rule | Points |
| --- | ---: |
| Latest close > EMA20 | 10 |
| EMA20 > EMA50 | 10 |
| EMA50 > EMA200 | 10 |

The scanner also reports `TrendStrength`, a 0-100 helper indicator based on EMA alignment, but the score currently uses the three explicit trend rules above.

## RSI momentum: 25 points

Based on RSI14:

| RSI14 Range | Points | Meaning |
| --- | ---: | --- |
| 50 to 70 | 25 | Healthy bullish momentum |
| >70 to 75 | 16 | Strong but becoming extended |
| >75 | 6 | Overextended; pullback risk is higher |
| 40 to <50 | 8 | Neutral to slightly weak |
| <40 | 0 | Weak momentum |

## MACD confirmation: 15 points

| MACD Condition | Points | Meaning |
| --- | ---: | --- |
| MACD > 0 and MACD histogram > 0 | 15 | Bullish momentum with acceleration |
| MACD histogram > 0 only | 10 | Momentum is improving |
| MACD > 0 only | 5 | Positive but not accelerating |
| Neither condition | 0 | MACD is not bullish |

## 20-bar price momentum: 15 points

```text
Momentum20 = percentage change between latest close and close 20 bars ago
```

| Momentum20 | Points | Meaning |
| --- | ---: | --- |
| >= 10% | 15 | Strong recent price momentum |
| >= 3% and < 10% | 12 | Positive recent price momentum |
| >= 0% and < 3% | 7 | Mildly positive momentum |
| < 0% | 0 | Negative momentum |

## Volume confirmation: 15 points

```text
Relative Volume 20 = latest volume / average volume of previous 20 bars
```

| Relative Volume 20 | Points | Meaning |
| --- | ---: | --- |
| >= 1.50 | 15 | Strong volume confirmation |
| >= 1.00 and < 1.50 | 11 | Supportive volume |
| >= 0.75 and < 1.00 | 6 | Slightly weak volume |
| < 0.75 | 0 | Weak volume confirmation |

## Why these were added before ATR/breakout

Current public sources show many high/low normalization warnings. EMA, RSI, MACD, momentum, and volume-based metrics depend mostly on close and volume fields, which are currently more reliable than high/low fields.

ATR, breakout detection, and candlestick patterns should be added after improving high/low confidence through more source validation.
