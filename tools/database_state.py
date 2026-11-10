"""Fail closed on missing/corrupt automation state; create consistent SQLite backups."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3


def check_database(path):
    path = Path(path).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Database integrity check failed")
        for table in ("source_prices", "scanner_signals", "scanner_runs"):
            if not conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]:
                raise ValueError(f"Restored database has no {table}")


def backup_database(source, destination):
    check_database(source)
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
    check_database(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "backup"))
    args = parser.parse_args()
    if args.action == "check":
        check_database("database/praecursor.db")
    else:
        backup_database("database/praecursor.db", "database/backup.db")
