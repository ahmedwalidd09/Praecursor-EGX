# Automated operation

GitHub Actions runs the scanner without the laptop being on. The existing encrypted
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets supply the bot credentials.

| Workflow | Schedule (UTC) | Work |
| --- | --- | --- |
| Outcome Learning | Sunday–Thursday, 17:15 | Refresh completed prices, verify saved predictions, export their original features, train and validate next-day and swing challengers. |
| Autonomous Scanner | Saturday–Wednesday, 18:30 | Collect prices, scan, save five eligible candidates with reasons, generate charts/dashboard, send the next-session Telegram briefing. Saturday prepares Sunday. |
| Official Disclosures | Sunday–Thursday, hourly at minute 12 from 06:00–17:00 | Archive partial official homepage disclosures and feed health. |
| Weekly Review | Thursday 20:15; Friday 08:15 recovery | Freeze the week's original top-five results, publish JSON/Markdown reports and send an owner Telegram review. Successful deliveries are recorded to suppress routine duplicates. |
| Automation Watchdog | Daily 21:45, 22:45, 23:45 | Check scheduled runs; dispatch one missing/failed workflow per check, at most one recovery per workflow/day. Active cloud jobs defer recovery to avoid replacing pending database writes. |
| Checks | Relevant pushes and pull requests | Run the offline regression suite. |
| Automation Alerts | Failed scanner, learning, disclosure, weekly, watchdog or check run | Send the configured owner a Telegram alert linking to the failed run. |

Cairo winter times are 19:15 for learning and 20:30 for the briefing; summer times
are one hour later. GitHub schedules can be delayed. Both scheduled workflows also
support **Run workflow** from the Actions page.

All work above executes on GitHub-hosted Ubuntu runners. The laptop, desktop
shortcut and local Python server can be off. A platform-wide GitHub outage can
also delay the watchdog; cron is not a guaranteed delivery deadline.

Each scan independently refreshes missing/stale quote-currency evidence for its
five candidates before paper sizing. Data audits cover every configured symbol,
including absent prices, conflicts, single-source coverage and currency gaps.
They preserve dated snapshots and queue official capital-action/suspension and
calendar notices. Public-feed gaps never become invented holiday dates or split
factors. Uncertain symbols remain watch-only under the existing risk rules.

Outcome verification anchors the entry for dated predictions to the next
configured session. A missing market-wide candle on that date leaves the result
unresolved. Resolved observations stay frozen under the label protocol, and later
vendor corrections remain in the price journal. Weekly
reports distinguish target hits/misses from profitable/loss/breakeven, unfilled,
ambiguous and unresolved trade scenarios. Missing results exclude the entire
paired session and remain counted. Weekly snapshots are immutable, with the
protocol hash, costs, uncertainty, matched-universe baseline and paper drawdown.
Their JSON/Markdown artifacts are retained for 90 days; snapshots persist in the DB.
The weekly period ends on Thursday at the 16:00 Cairo publication cutoff, including
weeks with a configured Thursday closure.

Filter trials run sequentially: observed-EGP turnover >= 1m, then positive
20-session momentum in >=60% of the saved universe. Original five picks and
filter decisions are frozen before the next open; excluded slots stay cash.
The first 60 trial sessions must all resolve, including conservative stop-first
returns for ambiguous barriers. Approval requires positive excess in at least
two 20-session blocks, a positive block-bootstrap lower bound and positive
returns after extra costs. Only approved filters affect future paper eligibility;
the most recently approved filter replaces the prior filter rather than stacking
untested rules. Its definition and approval timestamp enter each paper policy
snapshot. Live rankings are unchanged; model promotion uses its separate gates.
No trial is backfilled, thresholds are not tuned on the evaluation period, and
missing data cannot be silently skipped to reach 60 sessions.

Database-changing jobs share a concurrency group. Training runs separately and
does not hold that database lock, so the briefing can use the last accepted model
while a challenger is training. Price-only learning avoids scoring and publishing
a second set of predictions. Unchanged training inputs, protocol, and library
versions reuse the previous validation decision.

Only compatible features saved before the target session enter training. Missing
or unsettled outcomes stay pending. Chronological, maturity-purged validation,
calibration, and promotion gates remain mandatory; insufficient history or a
failed challenger keeps the incumbent. The initial holdout needs at least 40
sessions; promotion additionally requires three rolling tests, at least 140 mature
sessions and sufficient examples in every purged block. Collecting feedback
does not guarantee that a new model will be promoted each day.

The existing `db-latest` and `models-latest` release assets are mandatory state.
Missing downloads or corrupt/empty history fail the job instead of resetting it.
SQLite backups are checked before upload. Each database job retains a seven-day
recovery snapshot in its artifacts; reports/logs last 30 days and model evaluation
reports last 90 days. Recovery from a damaged release asset is a manual restore
from a successful run's snapshot, avoiding automatic rollback that could discard
newer predictions.

The local desktop dashboard still uses its local database. Cloud runs publish
their generated dashboard and reports as Actions artifacts; this workflow does
not turn the laptop dashboard into a hosted, automatically synchronized service.

Detailed implementation phases and remaining evidence gates: [institutional research roadmap](institutional_roadmap.md).
