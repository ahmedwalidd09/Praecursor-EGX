# Praecursor-EGX Predictor Labels

The scanner now separates three concepts:

1. Opportunity score: technical setup quality from indicators.
2. Consensus confidence: how strongly sources agree on latest close.
3. Data quality: warning-rate based quality of collected data.

The final predictor score combines these into one 0-100 value:

```text
Final Predictor Score =
    Opportunity Score * 0.75
  + Consensus Confidence * 0.15
  + Data Quality Score * 0.10
```

## Labels

| Label | Meaning |
| --- | --- |
| Strong Candidate | Strong final score, accepted consensus, and acceptable data quality. |
| Extended Breakout | Strong breakout setup but overextended RSI; entry timing risk is high. |
| Watchlist | Worth monitoring, but not strong enough for top-candidate status. |
| Low Confidence | Consensus is missing or rejected. |
| Low Data Quality | Data quality is too weak for a reliable decision. |
| Avoid | Weak technical setup under the current model. |

## Current important behavior

A stock can have a high opportunity score but still not be a clean buy candidate if:

- RSI is overextended.
- Volume is weak.
- Consensus confidence is only medium.
- Data quality is low.

Example: a volume-confirmed breakout with RSI above 75 may be labeled `Extended Breakout`, meaning it is strong but entry timing needs caution.
