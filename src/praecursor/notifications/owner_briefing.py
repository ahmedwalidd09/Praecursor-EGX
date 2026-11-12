"""Deliver the original dated shortlist to the configured Telegram owner."""
from datetime import datetime, timezone
from html import escape
import hmac
import json
import os
from pathlib import Path
import sqlite3

from praecursor.analysis.paper_portfolio import paper_summary
from praecursor.analysis.published_history import original_predictions
from praecursor.notifications.telegram import TelegramClient, TelegramReportFormatter, TelegramSettings


def original_shortlist(conn, session):
    return sorted((r for r in original_predictions(conn)
                   if r["target_session"] == session and r["candidate_rank"] in range(1, 6)),
                  key=lambda r: r["candidate_rank"])


def owner_settings():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token or chat or os.getenv("GITHUB_ACTIONS") == "true":
        return TelegramSettings(token, chat)
    return TelegramSettings.load()


def accepted_message(response, chat_id):
    result = response.get("result") or {}
    message_id = result.get("message_id")
    if (response.get("ok") is True and type(message_id) is int and message_id > 0
            and str((result.get("chat") or {}).get("id")) == chat_id):
        return message_id
    return None


def owner_settings_proof(settings, nonce):
    return hmac.digest(settings.bot_token.encode(), f"praecursor:{nonce}:{settings.chat_id}".encode(), "sha256").hex()


def deliver_owner_briefing(conn, session, charts_dir: Path, *, preview=False, refresh_incomplete=False):
    picks = original_shortlist(conn, session)
    if not picks:
        print(f"Telegram briefing unavailable for {session}: no original pre-open shortlist.")
        return 1
    for row in picks:
        row["selection_reasons"] = json.loads(row.get("selection_reasons") or "[]")
    conn.row_factory = sqlite3.Row
    message = TelegramReportFormatter().format_snapshot(dict(
        target_session=session, price_session=picks[0]["feature_session"], signals=picks, paper=paper_summary(conn)))
    message += "\n\nOriginal pre-open shortlist. Levels and reasons are from the saved scan."
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='quality_audits'").fetchone():
        audit = conn.execute("SELECT payload FROM quality_audits WHERE session=? ORDER BY checked_at DESC LIMIT 1",
                             (picks[0]["feature_session"],)).fetchone()
        if audit:
            quality = json.loads(audit[0])
            message += f"\nLatest audit: {quality['current_symbols']}/{quality['configured_symbols']} symbols had current prices."
    if refresh_incomplete:
        message += "\nThe current price refresh was incomplete. Review these saved levels with that limitation."
    if preview:
        print(message)
        return 0
    settings = owner_settings()
    if not settings.is_configured or len(message) > 4000:
        print("Telegram owner credentials or briefing length failed validation.")
        return 1
    proof = os.getenv("OWNER_SETTINGS_PROOF")
    if proof:
        nonce, _, digest = proof.partition(":")
        if not nonce or not hmac.compare_digest(digest, owner_settings_proof(settings, nonce)):
            print("Cloud owner settings differ from the expected configured pair.")
            return 1
        print("Cloud and local configured owner settings match.")
    conn.execute("""CREATE TABLE IF NOT EXISTS telegram_owner_receipts (
        session TEXT PRIMARY KEY, run_id INTEGER NOT NULL, message_id INTEGER NOT NULL, accepted_at TEXT NOT NULL)""")
    if conn.execute("SELECT 1 FROM telegram_owner_receipts WHERE session=?", (session,)).fetchone():
        print(f"Telegram owner briefing for {session} already accepted. Receipt reused.")
        return 0
    client = TelegramClient(settings)
    try:
        message_id = accepted_message(client.send_message(message, max_retries=1), settings.chat_id)
    except Exception:
        print("Telegram owner briefing request failed.")
        return 1
    if not message_id:
        print("Telegram did not confirm a message ID for the configured owner chat.")
        return 1
    conn.execute("INSERT INTO telegram_owner_receipts VALUES (?,?,?,?)",
                 (session, picks[0]["run_id"], message_id, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    print(f"Telegram accepted owner briefing for {session}: 1 recipient, message ID and chat verified.", flush=True)
    charts_sent = 0
    for row in picks:
        symbol = row["symbol"]
        chart = charts_dir / f"{session}_{symbol}_chart.png"
        if not chart.is_file():
            continue
        try:
            response = client.send_photo(chart, caption=f"{escape(symbol)} · Price history through {row['feature_session']}",
                                         reply_to_message_id=message_id)
            charts_sent += bool(accepted_message(response, settings.chat_id))
        except Exception:
            print(f"Telegram chart request failed for {symbol}.")
    print(f"Telegram accepted {charts_sent}/{len(picks)} original candidate charts for {session}.")
    return 0
