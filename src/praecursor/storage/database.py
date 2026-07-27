from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[3]
DATABASE = ROOT / "database" / "praecursor.db"


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection and make sure the database folder exists."""
    selected_path = database_path or DATABASE
    selected_path.parent.mkdir(parents=True, exist_ok=True)

    return sqlite3.connect(selected_path)
