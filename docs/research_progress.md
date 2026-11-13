# Praecursor research progress

## Reliability and data quality

Commit `7e4a938` anchored next-open verification, kept weekly reporting available
after configured Thursday closures, and made watchdog recovery check for work
across all database writers. CI passed 190 tests with 10 skipped. Both previews
completed. Recovery dispatch and deferral were exercised with run fixtures.
[CI](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/42974789548) ·
[Weekly preview](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/42974819909) ·
[Watchdog preview](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/42974815654)

## Horizon and shortlist integrity

An omitted middle session previously let a 21st-session target touch count in a
20-session swing outcome. Dated outcomes now keep every configured session
position. Fixtures cover the close cutoff, missing evidence, a configured
closure, the 20th-session boundary, late candle arrival and frozen outcomes.
[Regression fixtures](../tests/test_cloud_research.py)

The weekly preview regression previously showed three of five saved picks and
included that session in paired returns. Protocol `weekly-2` counts every saved
rank in the first pre-open run, matching dashboard prediction history. Training
eligibility is checked after selecting that run. Short legacy lists keep their
actual ranks. Paired estimates require five eligible picks and complete evidence
across the original eligible benchmark universe. [Weekly review workflow](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/workflows/weekly_review.yml)

Frozen outcomes and weekly snapshots are preserved. Current read paths treat
off-horizon outcomes as unverified, including for training and prospective trial
resolution. The November 11 cloud backup contained 610 horizon-aligned dated
next-day labels, zero resolved swing labels, zero frozen weekly reports and no
active promoted manifests. Two legacy shortlist entries with inferred dates
disagreed with the configured next session and are flagged as unverified.
The label formula and existing promotion gates still apply.
[Durable cloud state](https://github.com/ahmedwalidd09/Praecursor-EGX/releases/tag/db-latest)

## November 12 Telegram incident

The November 12 briefing was skipped after the Wednesday Actions schedule ran
early Thursday Cairo time. The old pipeline applied Thursday's evening scan
guard, logged November 15 as the target, and exited successfully without reaching
Telegram. [Skipped scheduled run](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43130940924)

The autonomous pipeline now derives the briefing date from the completed price
session and uses the original pre-open shortlist and chart dates. The owner route
uses the Actions credential pair directly. It requires Telegram's message ID and
matching response chat before recording a per-session receipt. Existing opt-in
subscriber tooling remains available separately. A lost response or failed
database persistence can still leave delivery uncertain. [Scanner workflow](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/workflows/daily_scan.yml)

The repaired November 12 cloud run used the November 11 completed price session
and matched the cloud owner settings to the local configuration before sending.
At 08:09 Cairo, Telegram acknowledged the briefing for one owner chat and all
five candidate charts. All six pipeline stages passed. The database backup
contained the five original picks with their reasons and one matching delivery
receipt. CI passed 198 tests with 10 skipped. [Repair commit](https://github.com/ahmedwalidd09/Praecursor-EGX/commit/19ca762) · [Live scanner](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43165765155) · [CI](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43165657254)

## Provider and instrument evidence

The November 12 baseline audit counted 207/248 current prices, all single-source,
and 239 currency gaps. Thirteen of the 37 missing or stale symbols were disabled
in the scan config. The cloud collection log recorded 22 StockAnalysis 404s.
Two current TradingView rows had zero volume. ARAB and GTEX showed disagreement
against the provider's two-decimal history table, which can be material for
sub-pound and sub-dollar shares. Those candles remain subject to normal conflict
checks. [Baseline audit](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43341840542) · [Collection log](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43322434690) · [ARAB history](https://stockanalysis.com/quote/egx/ARAB/history/) · [GTEX history](https://stockanalysis.com/quote/egx/GTEX/history/)

One impossible StockAnalysis candle could previously invalidate an entire
history response. The parser now omits the individual row and retains the
other validated dates. Currency evidence survives a rejected OHLCV response,
requires a matching EGX symbol, and gives explicit quote currency priority
over reporting currency. The audit now records provider freshness and the
latest known revision of Arabic and English official notices.
[COMI history](https://stockanalysis.com/quote/egx/COMI/history/) · [SAIB quote](https://stockanalysis.com/quote/egx/SAIB/)

After deploying `9be58b4`, a price-only cloud rerun used the same November 12
session. It saved current StockAnalysis observations for 170 symbols (previously
2), with 156 multi-source confirmations (previously zero). Currency gaps fell
from 239 to 53, with 188 EGP and 7 USD observations. Usable coverage fell from
207/248 (83.5%) to 195/248 (78.6%), or 195/235 enabled. Twelve additional
conflicts were exposed, leaving 14 conflicts, two invalid or no-trade rows,
and 37 stale or missing symbols. This measures the quality and completeness
of the evidence. The completed workflow saved the state and ran training behind
the existing promotion gates. CI passed 204 tests with 10 skipped.
[Deployment](https://github.com/ahmedwalidd09/Praecursor-EGX/commit/9be58b4) · [Cloud rerun and audit](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43420708386) · [CI](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43420677720)

The official homepage supplies recent notices and the EGX methodology describes
adjustment formulas. Neither establishes a complete historical closure calendar
or per-instrument effective dates and factors. The audit retains these items for
review without applying unverified closures or adjustments.
[Official notices](https://beta.egx.com.eg/en) · [EGX methodology](https://beta.egx.com.eg/api/media/uploads/EGX_100_EWI_Jan_2025_92e823d17f.pdf)

## Source mapping and display precision

The November 12 baseline contained 24 enabled symbols with no current price
observation, two invalid or no-trade rows and 14 provider conflicts. The price
refresh was applying the scoring minimum before reaching the second provider.
TWSA had 243 TradingView bars, below the scoring requirement of 251, while FCMD
had no TradingView response. Both StockAnalysis mappings resolve to the expected
companies. DEIN's public history showed dated rows with no reported trade
volume. These cases require separate evidence from a wrong ticker or a 404.
[Baseline cloud run](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43420708386) · [TWSA history](https://stockanalysis.com/quote/egx/TWSA/history/) · [FCMD history](https://stockanalysis.com/quote/egx/FCMD/history/) · [DEIN history](https://stockanalysis.com/quote/egx/DEIN/history/)

The price-only refresh now checks the second provider independently and judges
success on a usable candle for the completed session. Scoring still uses the
existing minimum history and eligibility checks. The audit flags conflicts
compatible with the two-decimal HTML display when all four price differences
fit a half-cent interval and reported volume is identical. These cases remain
conflicts for verification. ACGC and ELNA had close disagreements beyond that
interval despite matching intraday ranges. ARAB's saved baseline also had a
volume discrepancy, so it cannot be classified by price rounding alone.

No ticker was remapped from a name match or missing page. ALEX has a historical
issuer delisting statement and a current provider symbol, but the sources leave
current listing status unresolved. StockAnalysis supplies displayed values.
Investing.com requires permission for storing and reusing its market data.
FoudaLens limits automated collection, and its inspected archive did not
cover the target session. No independent full-precision feed was integrated.
[TITAN issuer history](https://titancementegypt.com/about-us/our-history/) · [TradingView ALEX](https://in.tradingview.com/symbols/EGX-ALEX/) · [Investing.com terms](https://www.investing.com/about-us/terms-and-conditions/) · [FoudaLens archive](https://foudalens.com/en/stock/ARAB.CA/trades) · [FoudaLens terms](https://foudalens.com/en/terms)

The November 12 cloud rerun on `9edd017` moved enabled coverage from 195/235
to 199/235. CPME, GOUR, KORA, and TWSA gained usable candles. Enabled symbols
with no current observation fell from 24 to 15, and invalid or no-trade rows
rose from two to seven as missing observations became visible. Currency gaps
fell from 53 to 42 across 248 configured symbols. Eight conflicts fit the
display check, and six had differences beyond it. All 14 remain unresolved.
Outcome Learning completed both jobs. CI passed 207 tests with 10 skipped.
[Cloud audit](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43422465160) · [CI](https://github.com/ahmedwalidd09/Praecursor-EGX/actions/runs/43422441563)

## Adaptive profit targets and stops

Implemented a prospective comparison of original saved targets and stops with
an adaptive challenger. One- and 20-session estimates use completed price
structure, a gap-aware noise buffer, and observed historical excursions. Both
arms use the same next-open eligibility, risk sizing and friction assumptions.
The trial remains shadow-only while paired evidence accumulates. Neither arm's
trial results enter production labels, model training, or active paper sizing.
[Methodology and archived-data example](adaptive_levels.md)

## Next work

- Resolve remaining missing instruments using authoritative listing status and
  provider mappings. Verify a licensed independent full-precision source before
  changing close or low-price conflict rules.
- Obtain authoritative exchange closure dates and corporate-action effective
  dates and factors. Keep collecting prospective evidence under the existing
  promotion gates.
