# Adaptive target and stop experiment

Baseline `0dc7bb4`. Next-day levels currently choose the nearest eligible
structural stop and target inside percentage bands, with clamped ATR fallbacks
and final 4% stop and 5% target defaults. Swing uses close plus 3 ATR and minus
1 ATR. Scanner scores, published levels, production labels, sizing, Telegram,
and charts continue to use those saved values during the experiment.

For example, the original November 12 EFIH next-day setup used a November 11
reference of 24.800, target 27.7664 and stop 23.272599. Gross reward per unit of
stop distance was 1.94. The chart's reference is the prior close.

This phase adds a protocol frozen prospectively against those same saved picks.

## Shadow protocol

`structure-excursion-shadow-1` freezes one comparison per candidate and horizon
from the first full pre-open shortlist. The reference is the completed close
`C`. The recent support `S` is the minimum low of five completed bars for the
next-day plan and 20 for swing. The noise fraction `v` is the median over 20
bars of `max(H-L, |H-prevClose|, |L-prevClose|) / prevClose`. The proposed stop
is `S - 0.25*C*v`. A break below that range plus the buffer invalidates the
setup. The coefficient is a fixed research assumption.

For each horizon `h` (one or 20 sessions), use 12 adjacent nonoverlapping
historical windows ending at or before the feature close. For each, compute
`max(futureHigh over h sessions)/windowStartClose - 1`. Multiply the current
close by one plus the median excursion. Cap the target at the nearest higher
local high from the last 21 candles with lower highs on both sides. Both
confirmation bars must have closed before publication. Session continuity
requires at least 21 candles for next-day and 241 for swing. Missing or
conflicting bars, flat data or discontinuities can leave a plan unavailable.
No parameters are optimized from the forward comparison. The median describes
past moves, not a calibrated target-touch probability.

At the close, gross reward/risk is `(T-C)/(C-S_stop)`. At an assumed entry
`E`, let `B=(1+friction)*(1+fee)` and `D=(1-friction)*(1-fee)`. Net
reward/risk is `(T*D-E*B)/(E*B-S_stop*D)`. Friction uses half the assumed
spread, slippage, and impact at the participation cap from the paper policy.
The stress scenario adds 25 bps per side. Both arms use the same cost
assumptions, minimum net ratio, equal nominal slots, gross/position/risk/turnover
caps, and retrospective daily volume cap. The shadow comparison is an isolated
slot experiment and does not model active sector or correlation allocations.

A simulated entry must be inside the barriers, within the lesser of `v` and
5% of the close, and pass the net ratio test at the next open. The cost-based
upper bound before the gap constraint is
`(T + minRR*S_stop)*D / ((1+minRR)*B)`. No observed spread, queue position,
slippage or broker fill is implied. Post-entry gap-through-stop uses the
opening price, same-bar ambiguity uses stop first, and timeout uses the last
close. Stops stay fixed. No exchange tick schedule was verified, so the
experiment uses full-precision analytical levels with display-only rounding
and produces no executable order prices.

Example using an archived, later November snapshot for illustration only.
EFIH had reference 24.800, recent low 23.100, median normalized true range
4.82%, and a stop estimate of 22.801. Median next-day favorable excursion was
1.96%, with a prior confirmed high at 25.100 capping the target. After costs,
the reference-close ratio was 0.02× and this arm stayed cash. This calculation
uses historical data as seen later and is excluded from prospective results.

## Evidence

The baseline uses original published levels with identical shadow entry,
sizing and cost rules. The snapshot preserves inputs, horizon dates, version,
quote currency, cost inputs and reasons. The paired report counts every slot,
including cash, and excludes sessions with unresolved potential fills from
paired performance. It includes fills and exit categories, net returns per fill
and per original candidate, payoff quartiles, cost sensitivity, observed holding
time, and an overlap-aware block bootstrap interval. Next-day drawdown uses the
paired session series. Swing drawdown remains unavailable because overlapping
cohorts cannot be treated as independent portfolios. Outcomes are frozen once
resolved. No shadow labels enter training or the paper book.

Wait for at least 60 prospective paired sessions and apply the existing
positive lower-bound, chronological consistency and stressed-return criteria
before considering a separate promotion decision. The current trial has no
promotion path. [True range](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr) · [Stop execution](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-15)
