import argparse
import sqlite3

from praecursor.storage.database import DATABASE, connect
from praecursor.storage.signal_history import SignalHistoryStore


def main() -> int:
    args = parse_args()

    SignalHistoryStore().initialize()

    print("Praecursor-EGX signal history")
    print(f"Database: {DATABASE}")
    print()

    with connect() as connection:
        connection.row_factory = sqlite3.Row
        runs = connection.execute(
            """
            SELECT id, generated_at, source_name, success_count, error_count, report_path
            FROM scanner_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()

        if not runs:
            print("No scanner runs stored yet. Run: python tools/run_scanner.py")
            return 0

        for run in runs:
            print("=" * 60)
            print(f"Run ID: {run['id']}")
            print(f"Generated at: {run['generated_at']}")
            print(f"Source: {run['source_name']}")
            print(f"Successful symbols: {run['success_count']}")
            print(f"Failed symbols: {run['error_count']}")
            print(f"Report: {run['report_path']}")
            print()
            print("Rank  Symbol  Final  Label              Previous  Change")
            print("----  ------  -----  -----------------  --------  ------")

            signals = connection.execute(
                """
                SELECT rank, symbol, final_predictor_score, predictor_label, previous_rank, rank_change
                FROM scanner_signals
                WHERE run_id = ?
                ORDER BY rank ASC
                """,
                (run["id"],),
            ).fetchall()

            for signal in signals:
                previous_rank = signal["previous_rank"] if signal["previous_rank"] is not None else "new"
                rank_change = format_rank_change(signal["rank_change"])
                print(
                    f"{signal['rank']:<4}  "
                    f"{signal['symbol']:<6}  "
                    f"{signal['final_predictor_score']:<5.0f}  "
                    f"{signal['predictor_label']:<17}  "
                    f"{previous_rank!s:<8}  "
                    f"{rank_change}"
                )

            print()

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show stored Praecursor-EGX scanner history.")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent runs to show. Default: 5.")
    return parser.parse_args()


def format_rank_change(value: int | None) -> str:
    if value is None:
        return "new"

    if value > 0:
        return f"up {value}"

    if value < 0:
        return f"down {abs(value)}"

    return "same"


if __name__ == "__main__":
    raise SystemExit(main())
