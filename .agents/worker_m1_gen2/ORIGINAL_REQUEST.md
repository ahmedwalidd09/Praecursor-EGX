## 2026-08-03T13:37:18Z
You are Worker 1 (Gen 2) for Praecursor-EGX Milestone 1 (Intraday Target Verification & Historical Archiving).
Working directory: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\worker_m1_gen2
Project root: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX
Explorer 1 Report: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\explorer_1\handoff.md
Scope document: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\orchestrator\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
Implement Requirement R2 (Intraday Target Verification) and Requirement R3 (Cumulative Historical Archive).

Detailed Instructions:
1. **Target Verification (R2)**:
   - In `src/praecursor/analysis/accuracy_tracker.py`:
     - Evaluate candidate target hit logic: `next_day_hit = 1 if high >= target_price else 0`.
     - Remove the `is_solid_gain = ((high - latest_close) / latest_close) >= 0.025` fallback that erroneously marked any +2.5% intraday gain as a HIT even when the calculated target was higher (e.g. 7.5%).
     - Ensure that if `intraday_high >= target_price`, it is recorded as a `HIT` (`next_day_hit = 1`) even if the closing price `close < target_price`.

2. **Cumulative Historical Archive (R3)**:
   - In `src/praecursor/analysis/accuracy_tracker.py` and `src/praecursor/storage/signal_history.py`:
     - Maintain persistent appending of daily signal evaluation outcomes to `scanner_signal_outcomes` in `database/praecursor.db`.
     - Preserve the 16 baseline historical evaluation records (8 candidates from 2026-08-01 run + 8 candidates from 2026-08-02 run).
     - Add cumulative history export function/CSV writer to generate `reports/archive/accuracy_history_archive.csv` maintaining running total accuracy metrics across multiple runs without overwriting prior records.

3. **Verification**:
   - Write comprehensive unit tests in `tests/test_accuracy_tracker.py` verifying:
     - Intraday high hitting target % logs as HIT even when close is lower.
     - Intraday high missing target % (even if > 2.5%) logs as MISS.
     - Running updater multiple times appends to history archive and maintains baseline count (16 records).
   - Run tests using `python -m unittest discover tests` or `pytest`.
   - Document commands and test results in `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\worker_m1_gen2\handoff.md`.

Send a message to parent when complete.
