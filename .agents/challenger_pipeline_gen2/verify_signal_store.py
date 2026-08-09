import os
import sqlite3
import tempfile
from pathlib import Path
from praecursor.storage.signal_history import SignalHistoryStore

def test_uninitialized_and_deleted_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_uninit.db"
        
        # Test 1: Non-existent file - Store creation auto-initializes
        print("--- Test 1: Non-existent file path ---")
        store = SignalHistoryStore(db_path)
        ranks = store.latest_ranks()
        print(f"Latest ranks on fresh empty DB: {ranks}")
        assert ranks == {}, f"Expected empty dict, got {ranks}"
        
        # Test 2: Table dropped post-init
        print("--- Test 2: Table dropped post-init ---")
        conn = sqlite3.connect(db_path)
        conn.execute("DROP TABLE scanner_runs")
        conn.commit()
        conn.close()
        
        # latest_ranks should catch OperationalError, call initialize(), and return {}
        ranks_after_drop = store.latest_ranks()
        print(f"Latest ranks after table drop: {ranks_after_drop}")
        assert ranks_after_drop == {}, f"Expected empty dict, got {ranks_after_drop}"
        
        # Test 3: Deleted DB file while instance active
        print("--- Test 3: File deleted on disk ---")
        if db_path.exists():
            db_path.unlink()
        ranks_after_delete = store.latest_ranks()
        print(f"Latest ranks after file delete: {ranks_after_delete}")
        assert ranks_after_delete == {}, f"Expected empty dict, got {ranks_after_delete}"
        
        print("ALL SIGNAL_HISTORY_STORE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_uninitialized_and_deleted_db()
