# Research upgrade phases and acceptance gates

This is a research system, not a claim of institutional certification, novelty or
demonstrated excess return. No broker execution is connected.

## Phase 1 — execution and portfolio controls

Implemented: prospective paper plans for the original daily top five; zero to five
positions; immutable policy snapshots; risk, sector, gross-exposure, correlation
and participation limits; a conservative daily OHLCV fill scenario; assumed fees,
spread and size-dependent impact; partial-fill bounds; gap handling; stop-first
ambiguity; unresolved-position freezes; drawdown and negative-expectancy pauses.
The initial EGP 100,000 is a hypothetical research account, not user capital.
Only recently observed EGP quote currencies can enter it. Risk policy is in
`config/paper_policy.json`; historical plans retain their original policy.

Acceptance: idempotency, missing-data handling, quote currencies, cash/exposure
limits and target/stop ambiguity tests pass. Realistic execution calibration still
needs observed intraday quotes/trades and broker fills. Daily volume is an ex-post
liquidity bound and is not treated as opening-auction liquidity.

## Phase 2 — evidence and public data

Implemented: official EGX public-homepage disclosure collection, Arabic/English
text, original-source links, publication and first-seen timestamps, immutable
revisions, conservative event tags, explicit factual earnings fields with excerpts,
feed-health status, quote-currency observations and a price observation journal.
The API endpoint rejected automated requests; the integration uses only readable
public homepage data. It does not bypass access controls or assume full coverage.

Known limitations: homepage disclosures are partial; the official price-history,
order-book and full delisted-instrument archives are not connected. Historical
universe reconstruction before collection remains incomplete. Corporate-action
factors and holiday overrides still require verified effective dates. The existing
`corporate_actions` records and `config/market_closures.json` remain authoritative;
raw headlines never automatically alter prices or declare an exchange holiday.
Recent capital-action/suspension disclosures conservatively block paper sizing
pending review; they are not presented as definitive live instrument status.

## Phase 3 — validation and experiment records

Implemented: three disjoint 20-session rolling tests with expanding training,
outcome-maturity purging, independent tuning/calibration, technical baselines,
five-session block-bootstrap excess-return intervals, preserved experiment records,
and a stricter live model contract. The original holdout must pass first; failed
challengers skip the expensive rolling fits. Rolling validation needs at least
140 mature sessions plus adequate purged blocks; the old 40-session gate alone
cannot promote a model. Retrospective reconstructions cannot promote live models.

The dashboard compares frozen published candidates against the matched eligible
universe and higher-cost scenarios. This universe is not an EGX index. A paper
portfolio provides separate prospective evidence. Repeated experiments and
uncertainty remain visible; these checks do not eliminate research overfitting.

## Phase 4 — disclosure hypothesis, kept separate from live scoring

Implemented: event cohorts join only announcements first seen before each saved
prediction; later discoveries never backfill a historical information advantage.
Financial fields are extracted as reported; growth, materiality, market-cap ratios
and sentiment are not inferred when comparable periods or units are unverified.
Disclosure classifications do not change live rankings or trained features.

Next evidence gate: collect enough independent event sessions, check extraction
against source documents, measure incremental returns after costs, then test a
versioned event-feature challenger on unseen periods. No evidence exists yet to
choose optimal event weights or claim a disclosure edge.

## Phase 5 — operations and observation

Implemented: scheduled official-disclosure collection, serialized database writes,
existing verified outcome/retraining/scanning workflows, backup integrity checks,
failure alerts, an offline regression suite and shared static/live dashboard views.
Public feeds may fail or change format; prior records survive failures and feed
health states remain visible. Disclosure collection runs hourly at minute 12 from
06:00–17:00 UTC, Sunday–Thursday. Other schedules remain in `automation.md`.

Fine-tuning is evidence-gated, not a one-turn promise: collect the forward ledger,
review missing data and execution assumptions, and retain a challenger only when
the protocol supports it. Paid feeds, full historic point-in-time data, broker
fills, live trading and desktop/cloud synchronization are not silently enabled.
