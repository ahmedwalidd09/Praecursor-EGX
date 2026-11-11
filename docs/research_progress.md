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

## Next work

- Make daily Telegram recovery reuse the original shortlist and persist a durable
  delivery receipt to suppress duplicates. The latest-scan briefing can still
  reflect a rerun.
- Investigate individual source gaps and currency evidence using observable
  provider and instrument records. The November 10 audit found 207 of 248
  symbols current and 246 currency gaps.
- Obtain authoritative exchange closure dates and corporate-action effective
  dates and factors. Unverified gaps remain unresolved.
