from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import argparse
import json
import sqlite3
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure") and stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from praecursor.notifications.telegram import TelegramClient, TelegramReportFormatter, TelegramSettings
from praecursor.storage.signal_history import SignalHistoryStore
from praecursor.workflows.scanner import ScannerWorkflow


@dataclass
class MinimalOppScore:
    latest_close: float
    company: str = ""


@dataclass
class MinimalResultRow:
    symbol: str
    next_day_score: float
    next_day_label: str
    opportunity_score: MinimalOppScore
    next_day_reasons: str = ""
    next_day_prediction: Any = None


@dataclass
class MinimalRunResult:
    generated_at: datetime
    success_count: int
    error_count: int
    next_day_results: list
    report_path: str = None
    markdown_report_path: str = None
    next_day_report_path: str = None
    dashboard_report_path: str = None


def load_latest_scan_result() -> MinimalRunResult | None:
    """Fetch latest scanner run results directly from database and calculate high-fidelity structural levels."""
    from praecursor.scoring.opportunity_score import OpportunityScore
    from praecursor.consensus.price_consensus import PriceConsensusResult
    from praecursor.scoring.next_day import calculate_next_day_prediction

    store = SignalHistoryStore()
    try:
        with store._connect() as conn:
            conn.row_factory = sqlite3.Row
            latest_run = conn.execute(
                "SELECT * FROM scanner_runs WHERE id IN (SELECT run_id FROM scanner_signals) ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not latest_run:
                return None

            run_id = latest_run["id"]
            gen_at_str = latest_run["generated_at"]
            if isinstance(gen_at_str, str):
                generated_at = datetime.fromisoformat(gen_at_str.replace('Z', '+00:00'))
            else:
                generated_at = datetime.now(timezone.utc)

            rows = conn.execute("SELECT * FROM scanner_signals WHERE run_id = ? ORDER BY rank ASC", (run_id,)).fetchall()

            symbol_results = []
            for r in rows:
                row = dict(r)
                sym = row.get("symbol", "UNKNOWN")
                comp = row.get("company", sym)
                latest_c = row.get("latest_close", 0.0) or 0.0
                opp_s = row.get("opportunity_score", 0.0) or 0.0

                ind_json = row.get("indicator_values_json")
                ind_values = {}
                if ind_json:
                    try:
                        ind_values = json.loads(ind_json)
                    except Exception:
                        ind_values = {}

                opp_score = OpportunityScore(
                    symbol=sym,
                    company=comp,
                    total_score=opp_s,
                    max_score=100,
                    indicator_values=ind_values,
                    latest_close=latest_c
                )

                consensus = None
                consensus_conf = row.get("consensus_confidence", 0.0) or 0.0
                if consensus_conf > 0:
                    consensus = PriceConsensusResult(
                        symbol=sym,
                        trade_date=generated_at.date(),
                        consensus_close=latest_c,
                        source_count=3,
                        agreeing_source_count=3,
                        target_source_count=3,
                        tolerance_percent=0.01,
                        minimum_agreeing_sources=2,
                        accepted=True,
                        agreements=[],
                        warnings=[]
                    )

                next_day_pred = calculate_next_day_prediction(
                    opportunity_score=opp_score,
                    consensus_accepted=consensus.accepted if consensus else False,
                    data_quality_score=row.get("data_quality_score", 100.0) or 100.0,
                )

                item = MinimalResultRow(
                    symbol=sym,
                    next_day_score=next_day_pred.score,
                    next_day_label=row.get("next_day_label") or next_day_pred.label,
                    opportunity_score=opp_score,
                    next_day_reasons=next_day_pred.reasons_text,
                    next_day_prediction=next_day_pred,
                )
                symbol_results.append(item)

            symbol_results = sorted(symbol_results, key=lambda x: x.next_day_score, reverse=True)

            # Top Pick badging matching workflow & dashboard
            top_pick_num = 0
            for i, res in enumerate(symbol_results):
                nd_pred = res.next_day_prediction
                label = res.next_day_label
                new_label = label
                is_eligible = ("Low Confidence" not in label) and ("Avoid" not in label)
                if nd_pred.score >= 68.0 and is_eligible and ("Candidate" in label) and top_pick_num < 5:
                    top_pick_num += 1
                    new_label = f"⭐ Top Pick #{top_pick_num} ({label})"
                if new_label != label:
                    res.next_day_label = new_label

            return MinimalRunResult(
                generated_at=generated_at,
                success_count=len(symbol_results),
                error_count=0,
                next_day_results=symbol_results,
                report_path=latest_run["report_path"],
                markdown_report_path=latest_run["markdown_report_path"],
                dashboard_report_path="reports/dashboard.html",
            )
    except Exception as e:
        return None


def main() -> int:
    args = parse_args()
    result = None

    if args.token and args.chat_id:
        settings = TelegramSettings(bot_token=args.token.strip(), chat_id=args.chat_id.strip())
        settings.save()
        print(f"[Telegram] Saved bot token and chat ID ({args.chat_id}) to config/telegram.json")
    else:
        settings = TelegramSettings.load()

    formatter = TelegramReportFormatter()

    dash_html = Path("reports/dashboard.html")
    if args.use_latest or (not args.run_scanner and not args.message):
        message = None
        if dash_html.exists():
            try:
                message = formatter.format_from_dashboard_html(dash_html, top_n=args.top)
            except Exception as e:
                logger.warning(f"Could not format from dashboard HTML: {e}")
        if not message:
            result = load_latest_scan_result()
            if result is None:
                print("Warning: No scanner runs found in database. Exiting cleanly.")
                return 0
            message = formatter.format_scanner_result(result, top_n=args.top)
    elif args.run_scanner:
        result = ScannerWorkflow().run(symbols=parse_symbols(args.symbols))
        message = formatter.format_scanner_result(result, top_n=args.top)
    elif args.message:
        message = args.message

    if result is None:
        result = load_latest_scan_result()

    if args.dry_run:
        print("\n--- TELEGRAM MESSAGE PREVIEW ---")
        print(message)
        print("--------------------------------\n")
        if not args.no_charts and result:
            charts_dir = Path("reports/charts")
            candidates = [c for c in getattr(result, "next_day_results", []) if "Avoid" not in getattr(c, "next_day_label", "")]
            candidates.sort(key=lambda x: getattr(x, "next_day_score", 0.0), reverse=True)
            top_actionable = candidates[:args.top_charts]
            print(f"--- CANDIDATE CHARTS QUEUED FOR PHOTO DISPATCH ({len(top_actionable)}) ---")
            for rank, item in enumerate(top_actionable, start=1):
                sym = getattr(item, "symbol", "")
                png = charts_dir / f"{sym}_chart.png"
                exists_tag = "[EXISTS]" if png.exists() else "[WILL GENERATE]"
                print(f"  Photo #{rank}: {sym} -> {png} {exists_tag}")
            print("----------------------------------------------------------\n")
        return 0

    if not settings.is_configured:
        print("[Telegram] [ERROR] Telegram credentials missing.")
        print("Please configure config/telegram.json or run:")
        print("python tools/send_telegram_report.py --token YOUR_TOKEN --chat-id YOUR_CHAT_ID")
        return 1

    client = TelegramClient(settings)
    resp = client.send_message(message, parse_mode="HTML")
    if resp.get("ok"):
        print(f"[Telegram] [SUCCESS] Scan report delivered to Chat ID {settings.chat_id}!")
    else:
        print(f"[Telegram] [ERROR] Delivery failed: {resp}")
        return 1

    if not args.no_charts and result is not None:
        from praecursor.notifications.telegram import dispatch_candidate_charts
        charts_sent = dispatch_candidate_charts(client, result=result, max_charts=args.top_charts, verbose=True)
        print(f"[Telegram] Delivered {charts_sent} visual technical radar charts as photos.")

    if args.send_files and result is not None:
        send_report_files(client, result)

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Praecursor-EGX scanner report to Telegram.")
    parser.add_argument("--token", help="Telegram Bot Token (saved to config/telegram.json)")
    parser.add_argument("--chat-id", help="Telegram Chat ID (saved to config/telegram.json)")
    parser.add_argument("--use-latest", action="store_true", help="Send summary from latest database scan run.")
    parser.add_argument("--run-scanner", action="store_true", help="Run scanner first and send its summary.")
    parser.add_argument("--symbols", help="Comma-separated symbols for scanner run, e.g. COMI,SWDY.")
    parser.add_argument("--message", help="Send a custom Telegram message instead of scanner output.")
    parser.add_argument("--top", type=int, default=5, help="Number of candidates per section. Default: 5.")
    parser.add_argument("--top-charts", type=int, default=3, help="Max number of candidate charts to send as photos. Default: 3.")
    parser.add_argument("--no-charts", action="store_true", help="Skip sending candlestick chart images.")
    parser.add_argument("--send-files", action="store_true", help="Also send CSV/HTML/Markdown report files.")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending to Telegram.")
    return parser.parse_args()


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def send_report_files(client: TelegramClient, result: Any) -> None:
    paths = [
        getattr(result, "next_day_report_path", None),
        getattr(result, "report_path", None),
        getattr(result, "markdown_report_path", None),
        getattr(result, "dashboard_report_path", None),
        getattr(result, "archive_report_path", None),
        getattr(result, "archive_markdown_report_path", None),
    ]
    for path in paths:
        if path:
            p = Path(path)
            if p.exists() and p.is_file():
                try:
                    client.send_document(p, caption=f"Praecursor-EGX report: {p.name}")
                    print(f"Telegram file sent: {p}")
                except Exception as e:
                    print(f"Warning: Failed to send {p} to Telegram: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
