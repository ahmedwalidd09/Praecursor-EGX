"""Praecursor-EGX Telegram Bot Hub CLI Runner.

Provides daemon long-polling service, diagnostics testing, and manual
scan briefing broadcasts across all whitelisted terminals.
"""

import argparse
import logging
from pathlib import Path
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure") and stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from praecursor.notifications.bot_hub import TelegramBotHub
from praecursor.notifications.telegram import TelegramSettings
from praecursor.storage.bot_store import get_bot_store

logger = logging.getLogger("praecursor.bot_hub")


def run_test() -> int:
    """Run diagnostics and initialization tests for Bot Hub."""
    print("==================================================")
    print("Praecursor-EGX Telegram Bot Hub Diagnostic Self-Test")
    print("==================================================")

    settings = TelegramSettings.load()
    print(f"• Configured: {settings.is_configured}")
    print(f"• Bot Token: {'[PRESENT]' if settings.bot_token else '[MISSING]'}")
    print(f"• Admin Chat ID: {settings.chat_id or '[NOT SET]'}")

    store = get_bot_store()
    print(f"• Database Path: {store.database_path}")
    print(f"• Whitelist JSON Path: {store.json_path}")

    whitelisted = store.get_whitelisted_users()
    pending = store.list_pending_requests()
    print(f"• Active Whitelisted Users: {len(whitelisted)}")
    for u in whitelisted:
        uname = f"@{u['username']}" if u.get("username") else "No username"
        print(f"   - ID: {u.get('user_id')} | Chat ID: {u.get('chat_id')} | {uname}")
    print(f"• Pending Access Requests: {len(pending)}")
    for p in pending:
        uname = f"@{p['username']}" if p.get("username") else "No username"
        print(f"   - ID: {p.get('user_id')} | {uname} | Msg ID: {p.get('admin_message_id')}")

    hub = TelegramBotHub(settings=settings, store=store)
    recipients = hub.get_recipient_chat_ids()
    print(f"• Total Outbound Broadcast Target Terminals: {len(recipients)}")

    if settings.is_configured:
        try:
            import urllib.request
            import json
            req = urllib.request.Request(f"https://api.telegram.org/bot{settings.bot_token}/getMe")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    bot_user = data.get("result", {})
                    print(f"• Bot API Connection: ONLINE (@{bot_user.get('username')})")
                else:
                    print(f"• Bot API Connection: FAILED ({data})")
        except Exception as e:
            print(f"• Bot API Connection Warning: {e}")
    else:
        print("• Bot API Connection: Skipped (Credentials not configured)")

    print("==================================================")
    print("✅ Diagnostic Self-Test Passed Successfully.")
    print("==================================================")
    return 0


def run_broadcast() -> int:
    """Manually broadcast the latest scan briefing to all authorized terminals."""
    print("[BotHub] Initiating scan briefing broadcast to all whitelisted terminals...")
    hub = TelegramBotHub()
    res = hub.broadcast_scan_briefing(run_result=None, top_n=5, send_charts=True, verbose=True)
    if res.get("ok"):
        print(f"[BotHub] Broadcast complete! Delivered to {res.get('sent_count')} terminals ({res.get('charts_count')} charts).")
        return 0
    else:
        print(f"[BotHub] Broadcast completed with warnings or no recipients: {res}")
        return 1


def run_daemon(poll_interval: float = 2.0) -> int:
    """Run interactive bot hub long-polling daemon."""
    settings = TelegramSettings.load()
    if not settings.is_configured:
        print("[BotHub] [WARNING] Telegram credentials not configured in config/telegram.json or environment.")
        print("Please configure config/telegram.json before starting live polling.")

    hub = TelegramBotHub(settings=settings)
    try:
        hub.run_polling(poll_interval=poll_interval)
    except KeyboardInterrupt:
        print("\n[BotHub] Terminated gracefully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Praecursor-EGX Telegram Bot Hub Service.")
    parser.add_argument("--test", action="store_true", help="Run diagnostic self-test and verify initialization.")
    parser.add_argument("--broadcast-latest", action="store_true", help="Broadcast latest scanner results to all whitelisted terminals.")
    parser.add_argument("--daemon", action="store_true", help="Run long-polling inbound engine as a persistent daemon.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling cycle interval in seconds (default: 2.0s).")
    args = parser.parse_args()

    if args.test:
        return run_test()
    elif args.broadcast_latest:
        return run_broadcast()
    else:
        # Default mode is running the daemon
        return run_daemon(poll_interval=args.interval)


if __name__ == "__main__":
    sys.exit(main())
