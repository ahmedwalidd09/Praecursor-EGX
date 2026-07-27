# Praecursor-EGX Scoring Model

Praecursor-EGX uses a transparent technical score. It is not a guarantee of future returns; it is a ranking heuristic to identify stocks that deserve further review.

## Current score: 100 points

| Category | Max Points | Purpose |
| --- | ---: | --- |
| Trend structure | 25 | Prefer stocks in a short/medium/long-term uptrend. |
| RSI momentum | 20 | Prefer healthy bullish momentum without excessive overextension. |
| MACD confirmation | 15 | Prefer positive MACD momentum and acceleration. |
| 20-bar price momentum | 10 | Prefer stocks with positive recent price performance. |
| Volume confirmation | 10 | Prefer moves supported by above-average volume. |
| Breakout setup | 20 | Prefer close-based breakouts and near-high setups. |

## Trend structure: 25 points

| Rule | Points |
| --- | ---: |
| Latest close > EMA20 | 8 |
| EMA20 > EMA50 | 8 |
| EMA50 > EMA200 | 9 |

The scanner also reports `TrendStrength`, a 0-100 helper indicator based on EMA alignment.

## RSI momentum: 20 points

| RSI14 Range | Points | Meaning |
| --- | ---: | --- |
| 50 to 70 | 20 | Healthy bullish momentum |
| >70 to 75 | 13 | Strong but becoming extended |
| >75 | 5 | Overextended; pullback risk is higher |
| 40 to <50 | 6 | Neutral to slightly weak |
| <40 | 0 | Weak momentum |

## MACD confirmation: 15 points

| MACD Condition | Points | Meaning |
| --- | ---: | --- |
| MACD > 0 and MACD histogram > 0 | 15 | Bullish momentum with acceleration |
| MACD histogram > 0 only | 10 | Momentum is improving |
| MACD > 0 only | 5 | Positive but not accelerating |
| Neither condition | 0 | MACD is not bullish |

## 20-bar price momentum: 10 points

```text
Momentum20 = percentage change between latest close and close 20 bars ago
```

| Momentum20 | Points | Meaning |
| --- | ---: | --- |
| >= 10% | 10 | Strong recent price momentum |
| >= 3% and < 10% | 8 | Positive recent price momentum |
| >= 0% and < 3% | 4 | Mildly positive momentum |
| < 0% | 0 | Negative momentum |

## Volume confirmation: 10 points

```text
Relative Volume 20 = latest volume / average volume of previous 20 bars
```

| Relative Volume 20 | Points | Meaning |
| --- | ---: | --- |
| >= 1.50 | 10 | Strong volume confirmation |
| >= 1.00 and < 1.50 | 7 | Supportive volume |
| >= 0.75 and < 1.00 | 4 | Slightly weak volume |
| < 0.75 | 0 | Weak volume confirmation |

## Breakout setup: 20 points

This model uses **closing-price breakouts**, not intraday-high breakouts, because close prices currently have better multi-source reliability than high/low values.

| Rule | Points |
| --- | ---: |
| Latest close > previous 20-bar highest close | 7 |
| Latest close > previous 50-bar highest close | 7 |
| Close within 3% of 250-bar closing high | 4 |
| Close within 7% of 250-bar closing high | 2 |
| Breakout is volume-confirmed | 2 |

The volume-confirmed breakout flag requires:

```text
Breakout20 = true
RelativeVolume20 >= 1.0
```

## ATR and volatility

The scanner reports:

```text
ATR14
ATRPercent14
```

ATR is not yet part of the opportunity score. It is currently informational because ATR depends on high/low values, and our public sources still produce high/low normalization warnings.

## High/low quality and ATR reliability

The scanner reports:

```text
high_low_quality_score
high_low_quality_label
atr_reliability_label
```

Current policy:

| High/Low Quality | ATR Reliability | Meaning |
| --- | --- | --- |
| >= 80 | usable | ATR can be considered more reliable. |
| >= 60 and < 80 | caution | ATR is useful for context, not final scoring. |
| < 60 | do_not_use | ATR should not be used for decisions. |

ATR/candlestick scoring should wait until high/low confidence improves through more source validation.
