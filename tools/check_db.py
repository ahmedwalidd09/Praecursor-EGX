import sqlite3
from pathlib import Path
from praecursor.analysis.accuracy_tracker import AccuracyTracker

def main():
    db_path = Path('database/praecursor.db')
    tracker = AccuracyTracker(db_path)
    tracker.update_historical_outcomes()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    outcomes = conn.execute("SELECT * FROM scanner_signal_outcomes ORDER BY signal_date ASC, run_id ASC, id ASC").fetchall()
    print(f"Total outcomes in scanner_signal_outcomes: {len(outcomes)}")
    for o in outcomes:
        print(dict(o))

if __name__ == '__main__':
    main()
