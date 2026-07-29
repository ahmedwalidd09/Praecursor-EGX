# Next-Day Prediction Lens

Praecursor-EGX is focused on finding stocks that may be ready for a strong move in the following trading session.

The live scanner now reports both:

```text
Final Predictor Score
Next-Day Score
```

## Final Predictor Score

This blends:

```text
Opportunity Score
Consensus Confidence
Data Quality
```

It answers:

> Is this a good overall technical candidate?

## Next-Day Score

This focuses more heavily on immediate move potential:

```text
TrendStrength
Breakout20
Breakout50
VolumeConfirmedBreakout
NearCloseHigh250Percent
MACDHistogram
Momentum20
RelVolume20
RSI overextension penalty
Consensus acceptance
Data quality
```

It answers:

> Is this setup likely to matter in the next trading session?

## Next-Day Labels

| Label | Meaning |
| --- | --- |
| Next-Day Explosion Candidate | Strong breakout, volume confirmation, and acceptable RSI. |
| Next-Day Explosion Candidate - Extended | Strong breakout but RSI is overextended; entry timing risk is high. |
| High-Priority Watch | Strong setup, but not a complete next-day explosion pattern. |
| Watchlist Tomorrow | Some evidence, but not enough for high-priority status. |
| Avoid Tomorrow | Weak next-day setup. |
| Low Confidence | Consensus is missing or rejected. |

## Backtesting

Backtesting now includes 1-bar and 2-bar horizons by default:

```text
1, 2, 5, 10, 20 bars
```

This makes the backtester more aligned with next-session prediction.
