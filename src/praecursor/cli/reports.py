import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT_ARCHIVE = ROOT / "reports" / "archive"


def main() -> int:
    args = parse_args()
    archive_files = sorted(REPORT_ARCHIVE.glob("opportunity_ranking_*.*"), reverse=True)

    print("Praecursor-EGX report archive")
    print(f"Archive directory: {REPORT_ARCHIVE}")
    print()

    if not archive_files:
        print("No archived reports found. Run: python tools/run_scanner.py")
        return 0

    for file_path in archive_files[: args.limit]:
        print(file_path)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List archived Praecursor-EGX scanner reports.")
    parser.add_argument("--limit", type=int, default=10, help="Number of archive files to show. Default: 10.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
