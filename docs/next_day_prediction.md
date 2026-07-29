# Next-Day Prediction Lens

Praecursor-EGX is focused on finding stocks that may be ready for a strong move in the following trading session.

The live scanner reports both:

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

The next-day model now has two separate lenses:

1. Breakout continuation
2. Early reversal / bounce

The final next-day score uses the stronger of those two lenses, then applies quality and overextension adjustments.

## Breakout continuation lens

Uses:

```text
TrendStrength
Breakout20
Breakout50
VolumeConfirmedBreakout
NearCloseHigh250Percent
MACDHistogram
Momentum20
RelVolume20
```

This looks for stocks already breaking out with volume.

## Early reversal lens

Uses:

```text
RSIRebound
EMA20Reclaim
MACDHistogramImprovement
VolumeSpikeFromWeakness
Momentum5
RSI14
Momentum20
RelVolume20
```

This looks for stocks that were weak but may be starting to reverse before a classic breakout appears.

## Next-Day Labels

| Label | Meaning |
| --- | --- |
| Next-Day Explosion Candidate | Strong breakout, volume confirmation, and acceptable RSI. |
| Next-Day Explosion Candidate - Extended | Strong breakout but RSI is overextended; entry timing risk is high. |
| Early Reversal Watch | Recovering from weakness with improving momentum/volume. |
| Reversal Watchlist | Some reversal evidence, but not strong enough yet. |
| High-Priority Watch | Strong setup, but not a complete explosion/reversal pattern. |
| Watchlist Tomorrow | Some evidence, but not enough for high-priority status. |
| Avoid Tomorrow | Weak next-day setup. |
| Low Confidence | Consensus is missing or rejected. |

## Backtesting

Backtesting includes 1-bar and 2-bar horizons by default:

```text
1, 2, 5, 10, 20 bars
```

This makes the backtester aligned with next-session prediction.

## Why Early Reversal was added

Backtest missed-mover reports showed many next-day jumps were not classic breakouts. They often came from weak or recovering stocks, so the model now separates:

```text
breakout continuation
early reversal / bounce
```
