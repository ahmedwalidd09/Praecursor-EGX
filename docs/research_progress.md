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

The official homepage supplies recent notices and the EGX methodology describes
adjustment formulas. Neither establishes a complete historical closure calendar
or per-instrument effective dates and factors. The audit retains these items for
review without applying unverified closures or adjustments.
[Official notices](https://beta.egx.com.eg/en) · [EGX methodology](https://beta.egx.com.eg/api/media/uploads/EGX_100_EWI_Jan_2025_92e823d17f.pdf)

## Next work

- Verify source mappings for enabled symbols with missing histories, and find
  full-precision independent daily prices for low-priced shares.
- Obtain authoritative exchange closure dates and corporate-action effective
  dates and factors. Keep collecting prospective evidence under the existing
  promotion gates.
