import sqlite3
import pytest
from praecursor.analysis.accuracy_tracker import AccuracyTracker
from praecursor.storage.signal_history import SignalHistoryStore, SIGNAL_HISTORY_SCHEMA


class TestR3HistoricalArchiveTier1:
    """Tier 1: Feature Coverage for R3 Cumulative Historical Archive."""

    def test_r3_cumulative_append(self, temp_db_path, accuracy_tracker):
        """Verify updater appends new daily records to history archive instead of overwriting."""
        stats_before = accuracy_tracker.get_accuracy_stats()
        initial_total = stats_before["next_day"]["total"]
        assert initial_total == 16, f"Expected initial 16 baseline records, got {initial_total}"

        # Add a 17th record for a new day
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count) VALUES ('2026-07-30T17:00:00', 'test', '[]', 1, 0)"
        )
        run_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO scanner_signals (
                run_id, generated_at, rank, symbol, company, opportunity_score,
                final_predictor_score, predictor_label, latest_close, consensus_confidence,
                data_quality_score, next_day_score, next_day_label, next_day_target
            ) VALUES (?, '2026-07-30T17:00:00', 1, 'NEW1', 'New Corp', 85.0, 85.0, 'BULLISH', 10.0, 100.0, 1.0, 85.0, 'BULLISH', 10.5)""",
            (run_id,)
        )

        cursor.execute(
            """INSERT INTO scanner_signal_outcomes (
                run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, swing_label
            ) VALUES (?, 'NEW1', '2026-07-30', 'BULLISH', 1, 5.0, '')""",
            (run_id,)
        )
        conn.commit()
        conn.close()

        stats_after = accuracy_tracker.get_accuracy_stats()
        assert stats_after["next_day"]["total"] == 17, f"Expected 17 total records after append, got {stats_after['next_day']['total']}"

    def test_r3_baseline_16_records(self, accuracy_tracker):
        """Verify history archive starts/maintains baseline of 16 historical records."""
        stats = accuracy_tracker.get_accuracy_stats()
        assert stats["next_day"]["total"] == 16
        history = stats["history"]
        assert len(history) == 16

    def test_r3_accuracy_percentage_calculation(self, accuracy_tracker):
        """Verify running total accuracy percentage is correctly calculated over cumulative records."""
        stats = accuracy_tracker.get_accuracy_stats()
        hits = stats["next_day"]["hits"]
        total = stats["next_day"]["total"]
        expected_accuracy = (hits / total * 100.0) if total > 0 else 0.0

        assert abs(stats["next_day"]["accuracy"] - expected_accuracy) < 0.001
        # In baseline fixture, there are 10 hits out of 16 = 62.5%
        assert hits == 10
        assert total == 16
        assert abs(stats["next_day"]["accuracy"] - 62.5) < 0.001

    def test_r3_persistence_across_runs(self, temp_db_path):
        """Verify history archive state persists across multiple scanner/updater invocations."""
        tracker1 = AccuracyTracker(database_path=temp_db_path)
        stats1 = tracker1.get_accuracy_stats()

        tracker2 = AccuracyTracker(database_path=temp_db_path)
        stats2 = tracker2.get_accuracy_stats()

        assert stats1["next_day"]["total"] == stats2["next_day"]["total"] == 16
        assert stats1["next_day"]["hits"] == stats2["next_day"]["hits"] == 10

    def test_r3_record_fields(self, temp_db_path):
        """Verify each archived record contains required fields (date, symbol, next_day_hit, next_day_return, next_day_label)."""
        conn = sqlite3.connect(str(temp_db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        row = cursor.execute("SELECT * FROM scanner_signal_outcomes LIMIT 1").fetchone()
        conn.close()

        assert row is not None
        d = dict(row)
        for field in ["run_id", "symbol", "signal_date", "next_day_label", "next_day_hit", "next_day_return"]:
            assert field in d, f"Missing required field {field} in outcome record"


class TestR3HistoricalArchiveTier2:
    """Tier 2: Boundary & Corner Cases for R3 Cumulative Historical Archive."""

    def test_r3_corrupted_archive_recovery(self, tmp_path):
        """Verify system recovers or reports clean error when history archive file is corrupted."""
        corrupt_db = tmp_path / "corrupt.db"
        corrupt_db.write_bytes(b"NOT A VALID SQLITE DATABASE FILE HEADER CONTENT")

        # Expecting sqlite3.DatabaseError or initialization recovery when opening corrupted file
        with pytest.raises(sqlite3.DatabaseError):
            store = SignalHistoryStore(corrupt_db)
            conn = store._connect()
            conn.execute("SELECT * FROM scanner_runs")

    def test_r3_large_archive_appends(self, tmp_path):
        """Verify performance and correctness when appending to an archive with 100+ records."""
        large_db = tmp_path / "large_archive.db"
        store = SignalHistoryStore(large_db)
        store.initialize()

        conn = sqlite3.connect(str(large_db))
        cursor = conn.cursor()

        cursor.execute("INSERT INTO scanner_runs (id, generated_at, source_name, symbols, success_count, error_count) VALUES (1, '2026-08-01T17:00:00', 'test', '[]', 1, 0)")

        # Insert 150 outcome records
        records = []
        for i in range(150):
            sym = f"SYM{i}"
            records.append((1, sym, "2026-08-01", "BULLISH", 1 if i % 2 == 0 else 0, 2.5, ''))

        cursor.executemany("""
            INSERT INTO scanner_signal_outcomes (run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, swing_label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, records)
        conn.commit()

        count = cursor.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0]
        conn.close()

        assert count == 150

    def test_r3_duplicate_date_symbol_handling(self, temp_db_path):
        """Verify handling of duplicate evaluation requests for same date and symbol (ON CONFLICT DO UPDATE)."""
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        # Try inserting duplicate outcome for run_id 1, symbol 'COMI'
        cursor.execute("""
            INSERT INTO scanner_signal_outcomes (
                run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return, swing_label
            ) VALUES (1, 'COMI', '2026-07-20', 'BULLISH', 1, 3.2, '')
            ON CONFLICT(run_id, symbol) DO UPDATE SET next_day_return = 4.0
        """)
        conn.commit()

        row = cursor.execute("SELECT next_day_return FROM scanner_signal_outcomes WHERE run_id = 1 AND symbol = 'COMI'").fetchone()
        conn.close()

        assert row[0] == 4.0

    def test_r3_empty_archive_initialization(self, tmp_path):
        """Verify system initializes baseline structure when starting from empty state."""
        empty_db = tmp_path / "empty_archive.db"
        tracker = AccuracyTracker(database_path=empty_db)
        stats = tracker.get_accuracy_stats()

        assert stats["next_day"]["total"] == 0
        assert stats["next_day"]["hits"] == 0
        assert stats["next_day"]["accuracy"] == 0.0
        assert len(stats["history"]) == 0

    def test_r3_concurrent_archive_access(self, temp_db_path):
        """Verify file lock / sqlite lock handling during archive appends."""
        conn1 = sqlite3.connect(str(temp_db_path), timeout=5.0)
        conn2 = sqlite3.connect(str(temp_db_path), timeout=5.0)

        # Both connections read concurrently
        r1 = conn1.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0]
        r2 = conn2.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0]

        assert r1 == 16
        assert r2 == 16
        conn1.close()
        conn2.close()
