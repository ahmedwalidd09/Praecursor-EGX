from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[3]

DATABASE = ROOT / "database" / "praecursor.db"


def connect():
    return sqlite3.connect(DATABASE)