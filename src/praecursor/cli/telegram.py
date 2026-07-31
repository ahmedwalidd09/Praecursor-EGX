import argparse
from pathlib import Path

from praecursor.notifications.telegram import TelegramClient, TelegramReportFormatter, TelegramSettings
from praecursor.workflows.scanner import ScannerWorkflow


def main() -> int:
    args = parse_args()
    result = None

    if args.run_scanner:
        result = ScannerWorkflow().run(symbols=parse_symbols(args.symbols))
        message = TelegramReportFormatter().format_scanner_result(result, top_n=args.top)
    elif args.message:
        message = args.message
    else:
        raise SystemExit("Use --run-scanner or --message.")

    if args.dry_run:
        print(message)
        return 0

    client = TelegramClient(TelegramSettings.from_environment())
    client.send_message(message)
    print("Telegram message sent.")

    if args.send_files and result is not None:
        send_report_files(client, result)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Praecursor-EGX scanner report to Telegram.")
    parser.add_argument("--run-scanner", action="store_true", help="Run scanner first and send its summary.")
    parser.add_argument("--symbols", help="Comma-separated symbols for scanner run, e.g. COMI,SWDY.")
    parser.add_argument("--message", help="Send a custom Telegram message instead of scanner output.")
    parser.add_argument("--top", type=int, default=5, help="Number of candidates per section. Default: 5.")
    parser.add_argument("--send-files", action="store_true", help="Also send CSV/HTML/Markdown report files.")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending to Telegram.")
    return parser.parse_args()


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def send_report_files(client: TelegramClient, result) -> None:
    paths = [
        result.next_day_report_path,
        result.swing_report_path,
        result.report_path,
        result.markdown_report_path,
        result.dashboard_report_path,
    ]
    for path in paths:
        if path and Path(path).exists():
            client.send_document(Path(path), caption=f"Praecursor-EGX report: {Path(path).name}")
            print(f"Telegram file sent: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
