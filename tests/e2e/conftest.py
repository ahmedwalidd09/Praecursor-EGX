import os
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice
from praecursor.storage.signal_history import SignalHistoryStore, SIGNAL_HISTORY_SCHEMA

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

BASELINE_RECORDS_DATA = [
    {"signal_date": "2026-07-20", "symbol": "COMI", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 3.2, "target_pct": 0.03, "latest_close": 80.0, "next_day_target": 82.4, "rank": 1},
    {"signal_date": "2026-07-20", "symbol": "EAST", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 4.1, "target_pct": 0.035, "latest_close": 25.0, "next_day_target": 25.875, "rank": 2},
    {"signal_date": "2026-07-21", "symbol": "HRHO", "next_day_label": "NEUTRAL", "next_day_hit": 0, "next_day_return": -1.1, "target_pct": 0.025, "latest_close": 18.5, "next_day_target": 18.96, "rank": 1},
    {"signal_date": "2026-07-21", "symbol": "SWDY", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 2.8, "target_pct": 0.02, "latest_close": 35.0, "next_day_target": 35.7, "rank": 2},
    {"signal_date": "2026-07-22", "symbol": "FWRY", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 5.0, "target_pct": 0.04, "latest_close": 6.2, "next_day_target": 6.448, "rank": 1},
    {"signal_date": "2026-07-22", "symbol": "TMGH", "next_day_label": "NEUTRAL", "next_day_hit": 0, "next_day_return": -0.5, "target_pct": 0.03, "latest_close": 55.0, "next_day_target": 56.65, "rank": 2},
    {"signal_date": "2026-07-23", "symbol": "AMOC", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 3.0, "target_pct": 0.025, "latest_close": 9.1, "next_day_target": 9.3275, "rank": 1},
    {"signal_date": "2026-07-23", "symbol": "EKHO", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 4.5, "target_pct": 0.03, "latest_close": 40.0, "next_day_target": 41.2, "rank": 2},
    {"signal_date": "2026-07-24", "symbol": "ESRS", "next_day_label": "NEUTRAL", "next_day_hit": 0, "next_day_return": -2.0, "target_pct": 0.04, "latest_close": 50.0, "next_day_target": 52.0, "rank": 1},
    {"signal_date": "2026-07-24", "symbol": "ABUK", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 3.5, "target_pct": 0.03, "latest_close": 75.0, "next_day_target": 77.25, "rank": 2},
    {"signal_date": "2026-07-27", "symbol": "ETEL", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 2.9, "target_pct": 0.025, "latest_close": 33.0, "next_day_target": 33.825, "rank": 1},
    {"signal_date": "2026-07-27", "symbol": "ORAS", "next_day_label": "NEUTRAL", "next_day_hit": 0, "next_day_return": 0.2, "target_pct": 0.03, "latest_close": 210.0, "next_day_target": 216.3, "rank": 2},
    {"signal_date": "2026-07-28", "symbol": "ISPH", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 4.0, "target_pct": 0.035, "latest_close": 3.5, "next_day_target": 3.6225, "rank": 1},
    {"signal_date": "2026-07-28", "symbol": "JUFO", "next_day_label": "NEUTRAL", "next_day_hit": 0, "next_day_return": -1.5, "target_pct": 0.02, "latest_close": 19.0, "next_day_target": 19.38, "rank": 2},
    {"signal_date": "2026-07-29", "symbol": "HELK", "next_day_label": "BULLISH", "next_day_hit": 1, "next_day_return": 3.8, "target_pct": 0.03, "latest_close": 15.0, "next_day_target": 15.45, "rank": 1},
    {"signal_date": "2026-07-29", "symbol": "CLHO", "next_day_label": "NEUTRAL", "next_day_hit": 0, "next_day_return": -0.8, "target_pct": 0.025, "latest_close": 5.8, "next_day_target": 5.945, "rank": 2},
]


@pytest.fixture
def baseline_records():
    return [dict(rec) for rec in BASELINE_RECORDS_DATA]


@pytest.fixture
def temp_db_path(tmp_path):
    db_file = tmp_path / "test_signal_history.db"
    store = SignalHistoryStore(db_file)
    store.initialize()

    # Populate 16 baseline records grouped by run_date
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    # Group baseline records by signal_date to insert runs
    dates = sorted(list(set(r["signal_date"] for r in BASELINE_RECORDS_DATA)))
    run_id_map = {}
    for d in dates:
        cursor.execute(
            """INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count)
               VALUES (?, 'consensus', '[]', 2, 0)""",
            (f"{d}T17:00:00",),
        )
        run_id_map[d] = cursor.lastrowid

    for r in BASELINE_RECORDS_DATA:
        run_id = run_id_map[r["signal_date"]]
        cursor.execute(
            """INSERT INTO scanner_signals (
                run_id, generated_at, rank, symbol, company, opportunity_score,
                final_predictor_score, predictor_label, latest_close, consensus_confidence,
                data_quality_score, next_day_score, next_day_label, next_day_target
            ) VALUES (?, ?, ?, ?, ?, 80.0, 85.0, ?, ?, 100.0, 1.0, 85.0, ?, ?)""",
            (
                run_id,
                f"{r['signal_date']}T17:00:00",
                r["rank"],
                r["symbol"],
                f"{r['symbol']} Corp",
                r["next_day_label"],
                r["latest_close"],
                r["next_day_label"],
                r["next_day_target"],
            ),
        )
        cursor.execute(
            """INSERT INTO scanner_signal_outcomes (
                run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, swing_label
            ) VALUES (?, ?, ?, ?, ?, ?, '')""",
            (
                run_id,
                r["symbol"],
                r["signal_date"],
                r["next_day_label"],
                r["next_day_hit"],
                r["next_day_return"],
            ),
        )

    conn.commit()
    conn.close()
    return db_file


@pytest.fixture
def accuracy_tracker(temp_db_path):
    return AccuracyTracker(database_path=temp_db_path)


@pytest.fixture
def consensus_engine():
    return PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def run_task_script(project_root):
    def _run(script_name="register_task.ps1", task_name="TestTask", time="17:00", extra_args=None):
        if script_name.endswith(".ps1"):
            script_path = project_root / script_name if not Path(script_name).is_absolute() else Path(script_name)
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path), task_name, time]
            if extra_args:
                cmd.extend(extra_args)
        elif script_name.endswith(".bat"):
            script_path = project_root / script_name if not Path(script_name).is_absolute() else Path(script_name)
            cmd = ["cmd.exe", "/c", str(script_path), task_name, time]
            if extra_args:
                cmd.extend(extra_args)
        else:
            raise ValueError(f"Unsupported script: {script_name}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    return _run
