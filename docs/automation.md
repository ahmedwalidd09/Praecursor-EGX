# Automated operation

GitHub Actions runs the scanner without the laptop being on. The existing encrypted
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` secrets supply the bot credentials.

| Workflow | Schedule (UTC) | Work |
| --- | --- | --- |
| Outcome Learning | Sunday–Thursday, 17:15 | Refresh completed prices, verify saved predictions, export their original features, train and validate next-day and swing challengers. |
| Autonomous Scanner | Saturday–Wednesday, 18:30 | Collect prices, scan, save five eligible candidates with reasons, generate charts/dashboard, send the next-session Telegram briefing. Saturday prepares Sunday. |
| Checks | Relevant pushes and pull requests | Run the offline regression suite. |
| Automation Alerts | Failed scanner, learning, or check run | Send the configured owner a Telegram alert linking to the failed run. |

Cairo winter times are 19:15 for learning and 20:30 for the briefing; summer times
are one hour later. GitHub schedules can be delayed. Both scheduled workflows also
support **Run workflow** from the Actions page.

Database-changing jobs share a concurrency group. Training runs separately and
does not hold that database lock, so the briefing can use the last accepted model
while a challenger is training. Price-only learning avoids scoring and publishing
a second set of predictions. Unchanged training inputs, protocol, and library
versions reuse the previous validation decision.

Only compatible features saved before the target session enter training. Missing
or unsettled outcomes stay pending. Chronological, maturity-purged validation,
calibration, and promotion gates remain mandatory; insufficient history or a
failed challenger keeps the incumbent. The current protocol needs at least 40
sessions and sufficient examples in each validation block. Collecting feedback
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
