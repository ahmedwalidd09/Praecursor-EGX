"""Export saved predictions exactly as published; never invent historical levels."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from praecursor.reporting.overview import overview
from praecursor.reporting.dashboard import ScannerDashboardWriter


def main():
    path=ScannerDashboardWriter().write_snapshot(overview())
    print(f"Saved prediction dashboard: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
