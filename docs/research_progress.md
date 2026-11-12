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

## Next work

- Investigate individual source gaps and currency evidence using observable
  provider and instrument records. The November 10 audit found 207 of 248
  symbols current and 246 currency gaps.
- Obtain authoritative exchange closure dates and corporate-action effective
  dates and factors. Unverified gaps remain unresolved.
