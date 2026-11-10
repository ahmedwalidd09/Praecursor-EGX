from datetime import date
import json
import sqlite3
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from praecursor.collectors.fake_market_data_source import FakeMarketDataSource
from praecursor.storage.price_cache import PriceCache
from praecursor.workflows.scanner import ScannerWorkflow
from tools.database_state import check_database, backup_database
from tools.notify_workflow_failure import failure_message
from tools.run_autonomous_pipeline import run_pipeline
from tools.track_outcomes import track_outcomes


def test_prices_only_collects_without_scoring_or_publishing(tmp_path):
    scorer = Mock()
    scorer.score.side_effect = AssertionError("Prices refresh must not score")
    workflow = ScannerWorkflow(lookback_days=450, minimum_bars=200,
        source_name="fake_market_data", market_data_source=FakeMarketDataSource(),
        price_cache=PriceCache(database_path=tmp_path / "prices.db"),
        enable_consensus=False, scorer=scorer)
    with patch.object(workflow.report_writer, "write") as reports, \
         patch.object(workflow.dashboard_writer, "write") as dashboard, \
         patch.object(workflow.history_store, "save_run") as history:
        result = workflow.run(symbols=["COMI", "HRHO"], end_date=date(2026, 7, 27), prices_only=True)
    assert result.success_count == 2 and not result.errors
    assert result.history_run_id is None and result.report_path is None
    assert workflow.price_cache.count("COMI", "fake_market_data") > 200
    for operation in (scorer.score, reports, dashboard, history):
        operation.assert_not_called()


def test_database_backup_requires_real_history_and_preserves_it(tmp_path):
    source, backup = tmp_path / "state.db", tmp_path / "backup.db"
    with pytest.raises(sqlite3.OperationalError):
        check_database(source)
    assert not source.exists()
    with sqlite3.connect(source) as conn:
        for table in ("source_prices", "scanner_signals", "scanner_runs"):
            conn.execute(f"CREATE TABLE {table} (id)")
            conn.execute(f"INSERT INTO {table} VALUES (1)")
    backup_database(source, backup)
    check_database(backup)
    with sqlite3.connect(source) as conn:
        conn.execute("DELETE FROM scanner_signals")
    with pytest.raises(ValueError, match="scanner_signals"):
        backup_database(source, backup)
    check_database(backup)
    source.write_bytes(b"corrupted")
    with pytest.raises(sqlite3.DatabaseError):
        check_database(source)


def test_scoring_failure_excludes_symbol_without_aborting_scan(tmp_path):
    workflow = ScannerWorkflow(lookback_days=450, minimum_bars=200,
        source_name="fake_market_data", market_data_source=FakeMarketDataSource(),
        price_cache=PriceCache(database_path=tmp_path / "prices.db"),
        enable_consensus=False, enable_history=False, enable_archive_reports=False)
    real_score = workflow.scorer.score
    def score(stock):
        if stock.symbol == "COMI":
            raise ValueError("Invalid indicator input")
        return real_score(stock)
    with patch.object(workflow.scorer, "score", side_effect=score) as scorer, \
         patch.object(workflow.report_writer, "write"), \
         patch.object(workflow.markdown_report_writer, "write"), \
         patch.object(workflow.dashboard_writer, "write"):
        result = workflow.run(symbols=["COMI", "HRHO"], end_date=date(2026, 7, 27))
    assert result.success_count == 1 and result.errors == {"COMI": "Invalid indicator input"}
    assert scorer.call_count == 2  # One scoring pass after market context is available.


def test_outcome_errors_are_not_reported_as_success(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        track_outcomes(tmp_path / "missing.db")
    with patch("tools.track_outcomes.check_database"), \
         patch("tools.track_outcomes.AccuracyTracker.evaluate_outcomes", side_effect=RuntimeError("broken")):
        with pytest.raises(RuntimeError, match="broken"):
            track_outcomes(tmp_path / "missing.db")
    with patch("tools.run_autonomous_pipeline.run_stage", side_effect=[True, False, True, True, True]):
        assert run_pipeline(tmp_path, tmp_path / "logs", run_date=date(2026, 11, 7)) == 1
    assert not json.loads((tmp_path / "data/scan_status.json").read_text())["completed"]


def test_training_reuses_same_input_but_reacts_to_labels_and_protocol(tmp_path, monkeypatch):
    from tools import retrain_models as training
    original_root = training.ROOT
    for name in ("src/praecursor/ml/validation.py", "src/praecursor/ml/features.py",
                 "src/praecursor/analysis/outcomes.py", "src/praecursor/ml/rolling.py", "tools/retrain_models.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((original_root / name).read_bytes())
    monkeypatch.setattr(training, "ROOT", tmp_path)
    trainer = Mock(side_effect=lambda *args, **kwargs: dict(status="evaluated", promoted=False))
    monkeypatch.setattr(training, "train_validate", trainer)
    frame = pd.DataFrame(dict(session=["2026-11-05", "2026-11-04"], symbol=["A", "B"],
                              next_day_target_hit=[1, 0], swing_target_hit=[None, None]))
    training.train_published_if_changed(frame, "next_day")
    assert training.train_published_if_changed(frame.iloc[::-1], "next_day")["reused_validation"]
    frame.loc[0, "swing_target_hit"] = 1
    training.train_published_if_changed(frame, "next_day")
    assert trainer.call_count == 1
    frame.loc[0, "next_day_target_hit"] = 0
    training.train_published_if_changed(frame, "next_day")
    assert trainer.call_count == 2
    with (tmp_path / "src/praecursor/ml/validation.py").open("a") as f:
        f.write("\n# revised protocol\n")
    training.train_published_if_changed(frame, "next_day")
    assert trainer.call_count == 3
    assert trainer.call_args_list[1].kwargs["input_fingerprint"] != trainer.call_args_list[2].kwargs["input_fingerprint"]


def test_alert_escapes_workflow_text():
    assert "Scanner &lt;failed&gt;" in failure_message("Scanner <failed>", "https://github.com/run")
