"""Build the frozen weekly review and optionally deliver it to the existing owner bot."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from praecursor.storage.database import connect
from praecursor.analysis.research import measurement_samples
from praecursor.analysis.data_quality import audit_data
from praecursor.analysis.shadow_experiments import resolve_shadows
from praecursor.analysis.weekly_report import completed_week, freeze_weekly, build_weekly, format_weekly


def send_owner(text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise RuntimeError("Telegram Actions secrets are missing")
    body = json.dumps(dict(chat_id=chat,text=text,disable_web_page_preview=True)).encode()
    request = Request(f"https://api.telegram.org/bot{token}/sendMessage",data=body,
                      headers={"Content-Type":"application/json"})
    try:
        with urlopen(request,timeout=30) as response:
            if not json.load(response).get("ok"):
                raise ValueError("Rejected report")
    except Exception:
        raise RuntimeError("Weekly Telegram delivery failed; credentials withheld") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    end = completed_week(now)
    with closing(connect(ROOT / "database/praecursor.db")) as conn:
        audit_data(conn,now)
        resolve_shadows(conn,now)
        frame = measurement_samples(conn)
        report = (build_weekly if args.dry_run else freeze_weekly)(conn,frame,end,now)
        message = format_weekly(report)
        output = ROOT / "reports"
        output.mkdir(exist_ok=True)
        (output / "weekly_review.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
        (output / "weekly_review.md").write_text(message,encoding="utf-8")
        if not args.dry_run:
            previous = conn.execute("SELECT delivery_status FROM weekly_reports WHERE week_end=?",(end.isoformat(),)).fetchone()[0]
            if previous != "sent":
                send_owner(message)
                conn.execute("UPDATE weekly_reports SET delivery_status='sent' WHERE week_end=?",(end.isoformat(),))
                conn.commit()
        print(message)
        print("Preview only; no Telegram sent" if args.dry_run else "Weekly report delivered or already sent")


if __name__ == "__main__":
    main()
