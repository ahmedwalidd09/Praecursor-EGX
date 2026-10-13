from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import sys
import time
from typing import Any

from praecursor.notifications.telegram import (
    TelegramClient,
    TelegramReportFormatter,
    TelegramSettings,
    dispatch_candidate_charts,
)
from praecursor.storage.bot_store import BotAccessStore, get_bot_store

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TelegramBotHub:
    """Dual-functional Telegram Bot Hub for Praecursor-EGX.

    Provides outbound broadcast of daily scans to all whitelisted terminals,
    along with an inbound long-polling engine supporting interactive permission-slip
    and reply-to-approve access control.
    """

    def __init__(
        self,
        settings: TelegramSettings | None = None,
        client: TelegramClient | None = None,
        store: BotAccessStore | None = None,
    ):
        self.settings = settings or TelegramSettings.load()
        self.client = client or TelegramClient(self.settings)
        self.store = store or get_bot_store()
        self.formatter = TelegramReportFormatter()
        self.admin_chat_id = str(self.settings.chat_id).strip()
        self.last_update_id = 0
        self._ensure_admin_registered()

    def _ensure_admin_registered(self) -> None:
        """Ensure super-admin chat ID is recognized in the whitelist."""
        if self.admin_chat_id:
            try:
                admin_id_int = int(self.admin_chat_id)
                if not self.store.is_whitelisted(admin_id_int):
                    self.store.add_whitelisted(
                        chat_id=admin_id_int,
                        user_id=admin_id_int,
                        username="SuperAdmin",
                        first_name="Admin",
                        last_name="",
                        pin="SUPERADMIN",
                    )
            except ValueError:
                pass

    def is_admin(self, user_or_chat_id: int | str) -> bool:
        """Check if user or chat ID is the super administrator."""
        return str(user_or_chat_id).strip() == self.admin_chat_id

    # =========================================================================
    # Outbound Broadcast
    # =========================================================================

    def get_recipient_chat_ids(self) -> list[int]:
        """Fetch all unique active chat IDs authorized to receive scan briefings."""
        recipients: set[int] = set()
        if self.admin_chat_id:
            try:
                recipients.add(int(self.admin_chat_id))
            except ValueError:
                pass

        users = self.store.get_whitelisted_users()
        for u in users:
            cid = u.get("chat_id")
            if cid:
                recipients.add(int(cid))
        return sorted(recipients)

    def broadcast_scan_briefing(
        self,
        run_result: Any = None,
        top_n: int = 5,
        send_charts: bool = True,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """Broadcast formatted daily scan briefing and charts to all active whitelisted terminals."""
        if run_result is None:
            try:
                from praecursor.cli.telegram import load_latest_scan_result
                run_result = load_latest_scan_result()
            except Exception as e:
                logger.warning(f"Could not load scan result for broadcast: {e}")

        # Format message from dashboard HTML if present, else run_result
        dash_html = PROJECT_ROOT / "reports" / "dashboard.html"
        message = None
        if dash_html.exists():
            try:
                message = self.formatter.format_from_dashboard_html(dash_html, top_n=top_n)
            except Exception:
                pass
        if not message and run_result:
            message = self.formatter.format_scanner_result(run_result, top_n=top_n)

        if not message:
            logger.warning("No scan message could be generated for broadcast.")
            return {"ok": False, "sent_count": 0, "charts_count": 0}

        recipients = self.get_recipient_chat_ids()
        if verbose:
            print(f"[BotHub] Broadcasting scan report to {len(recipients)} authorized terminals...")

        sent_messages = 0
        total_charts = 0

        for chat_id in recipients:
            try:
                resp = self.client.send_message(message, chat_id=chat_id, parse_mode="HTML")
                if resp.get("ok"):
                    sent_messages += 1
                    if send_charts and run_result:
                        charts_sent = dispatch_candidate_charts(
                            self.client,
                            result=run_result,
                            max_charts=top_n,
                            verbose=verbose,
                            chat_id=chat_id,
                        )
                        total_charts += charts_sent
            except Exception as e:
                logger.error(f"[BotHub] Failed to send scan briefing to {chat_id}: {e}")

        if verbose:
            print(f"[BotHub] Broadcast complete: {sent_messages}/{len(recipients)} terminals delivered.")

        return {
            "ok": True,
            "recipients_count": len(recipients),
            "sent_count": sent_messages,
            "charts_count": total_charts,
        }

    def broadcast_message(self, text: str, verbose: bool = True) -> int:
        """Broadcast custom text announcement to all whitelisted terminals."""
        recipients = self.get_recipient_chat_ids()
        sent = 0
        for chat_id in recipients:
            try:
                resp = self.client.send_message(text, chat_id=chat_id, parse_mode="HTML")
                if resp.get("ok"):
                    sent += 1
            except Exception as e:
                logger.error(f"[BotHub] Error broadcasting to {chat_id}: {e}")
        return sent

    # =========================================================================
    # Inbound Message Processing & Flow Execution
    # =========================================================================

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Dispatch and process an individual incoming Telegram message."""
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        from_user = message.get("from", {})
        user_id = from_user.get("id", chat_id)
        username = from_user.get("username", "") or ""
        first_name = from_user.get("first_name", "") or ""
        last_name = from_user.get("last_name", "") or ""
        language_code = from_user.get("language_code", "en") or "en"
        text = (message.get("text") or "").strip()
        reply_to = message.get("reply_to_message")
        msg_id = message.get("message_id")

        if not chat_id or not user_id:
            return {"action": "ignored", "reason": "no_chat_or_user_id"}

        is_admin_user = self.is_admin(chat_id) or self.is_admin(user_id)

        # ---------------------------------------------------------------------
        # 1. Administrator Flow
        # ---------------------------------------------------------------------
        if is_admin_user:
            # (A) Reply-to-Approve Flow
            if reply_to and text:
                reply_msg_id = reply_to.get("message_id")
                pending = self.store.get_pending_by_admin_message_id(reply_msg_id)
                if pending:
                    pin = text.strip()
                    target_uid = pending["user_id"]
                    target_cid = pending["chat_id"]
                    target_uname = pending.get("username") or f"User_{target_uid}"

                    self.store.assign_pin_to_request(target_uid, pin)

                    # Send approval notification to target user
                    user_msg = (
                        f"🔑 Access Approved by Administrator!\n"
                        f"Your activation code is: <b>{pin}</b>\n\n"
                        f"Enter your code now to activate:\n"
                        f"<code>/pin {pin}</code>"
                    )
                    self.client.send_message(user_msg, chat_id=target_cid, parse_mode="HTML")

                    # Reply to administrator
                    admin_msg = (
                        f"✅ Approved @{target_uname} (ID: <code>{target_uid}</code>) with code: <b>{pin}</b>.\n"
                        f"User has been notified! Ready for next request."
                    )
                    self.client.send_message(
                        admin_msg,
                        chat_id=chat_id,
                        parse_mode="HTML",
                        reply_to_message_id=msg_id,
                    )
                    return {"action": "admin_reply_approved", "user_id": target_uid, "pin": pin}

            # (B) Admin Commands
            parts = text.split()
            cmd = parts[0].lower() if parts else ""

            if cmd == "/code" and len(parts) >= 3:
                try:
                    target_uid = int(parts[1])
                    pin = parts[2].strip()
                    self.store.assign_pin_to_request(target_uid, pin)
                    pending = self.store.get_pending_by_user(target_uid)
                    if pending:
                        target_cid = pending["chat_id"]
                        user_msg = (
                            f"🔑 Access Approved by Administrator!\n"
                            f"Your activation code is: <b>{pin}</b>\n\n"
                            f"Enter your code now to activate:\n"
                            f"<code>/pin {pin}</code>"
                        )
                        self.client.send_message(user_msg, chat_id=target_cid, parse_mode="HTML")
                        self.client.send_message(
                            f"✅ Assigned code <b>{pin}</b> to user <code>{target_uid}</code>. User notified!",
                            chat_id=chat_id,
                            parse_mode="HTML",
                        )
                    else:
                        self.client.send_message(
                            f"✅ Assigned PIN <b>{pin}</b> to user <code>{target_uid}</code> (registered in PIN store).",
                            chat_id=chat_id,
                            parse_mode="HTML",
                        )
                    return {"action": "admin_code_assigned", "user_id": target_uid, "pin": pin}
                except ValueError:
                    self.client.send_message("⚠️ Invalid format. Usage: <code>/code &lt;user_id&gt; &lt;PIN&gt;</code>", chat_id=chat_id, parse_mode="HTML")
                    return {"action": "admin_error", "reason": "invalid_code_syntax"}

            elif cmd == "/pending":
                pending_list = self.store.list_pending_requests()
                if not pending_list:
                    self.client.send_message("📋 <b>Pending Queue:</b> Empty. No unapproved users.", chat_id=chat_id, parse_mode="HTML")
                else:
                    lines = ["📋 <b>Pending Access Requests:</b>\n"]
                    for p in pending_list:
                        uname = f"@{p['username']}" if p.get("username") else "No username"
                        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Anonymous"
                        req_time = p.get("requested_at", "")[:19].replace("T", " ")
                        lines.append(
                            f"• <b>{name}</b> ({uname})\n"
                            f"  ID: <code>{p['user_id']}</code> | Time: {req_time}\n"
                            f"  Approve: <code>/code {p['user_id']} PIN</code>\n"
                        )
                    self.client.send_message("\n".join(lines), chat_id=chat_id, parse_mode="HTML")
                return {"action": "admin_pending_listed"}

            elif cmd == "/whitelist":
                users = self.store.get_whitelisted_users()
                if not users:
                    self.client.send_message("📋 No whitelisted users found.", chat_id=chat_id, parse_mode="HTML")
                else:
                    lines = [f"🛡️ <b>Whitelisted Terminals ({len(users)}):</b>\n"]
                    for u in users:
                        uname = f"@{u['username']}" if u.get("username") else "No username"
                        name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "User"
                        lines.append(f"• <b>{name}</b> ({uname}) | ID: <code>{u.get('user_id', u.get('chat_id'))}</code>")
                    self.client.send_message("\n".join(lines), chat_id=chat_id, parse_mode="HTML")
                return {"action": "admin_whitelist_listed"}

            elif cmd == "/revoke" and len(parts) >= 2:
                try:
                    target_uid = int(parts[1])
                    revoked = self.store.remove_whitelisted(target_uid)
                    msg = f"🚫 Revoked authorization for user <code>{target_uid}</code>." if revoked else f"⚠️ User <code>{target_uid}</code> was not found or already revoked."
                    self.client.send_message(msg, chat_id=chat_id, parse_mode="HTML")
                    return {"action": "admin_revoked", "user_id": target_uid}
                except ValueError:
                    self.client.send_message("Usage: <code>/revoke &lt;user_id&gt;</code>", chat_id=chat_id, parse_mode="HTML")
                    return {"action": "admin_error", "reason": "invalid_revoke_syntax"}

            elif cmd == "/broadcast" and len(parts) >= 2:
                broadcast_body = text[len("/broadcast"):].strip()
                sent_cnt = self.broadcast_message(broadcast_body)
                self.client.send_message(f"📢 Broadcast sent to <b>{sent_cnt}</b> terminals.", chat_id=chat_id, parse_mode="HTML")
                return {"action": "admin_broadcast", "count": sent_cnt}

            elif cmd == "/setpin" and len(parts) >= 2:
                pin_code = parts[1].strip()
                uid_opt = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else None
                self.store.create_pin(pin_code, uid_opt)
                target_str = f" for user <code>{uid_opt}</code>" if uid_opt else ""
                self.client.send_message(f"🔑 PIN <b>{pin_code}</b> pre-created{target_str}.", chat_id=chat_id, parse_mode="HTML")
                return {"action": "admin_setpin", "pin": pin_code}

        # ---------------------------------------------------------------------
        # 2. Whitelisted Users Flow (or Admin using terminal commands)
        # ---------------------------------------------------------------------
        is_user_whitelisted = self.store.is_whitelisted(chat_id) or is_admin_user

        if is_user_whitelisted:
            parts = text.split()
            cmd = parts[0].lower() if parts else ""

            if cmd in ("/report", "/scan"):
                self._send_latest_report(chat_id)
                return {"action": "whitelisted_report"}

            elif cmd == "/top5":
                self._send_top5_with_charts(chat_id)
                return {"action": "whitelisted_top5"}

            elif cmd == "/chart":
                sym = parts[1].upper() if len(parts) >= 2 else ""
                if sym:
                    self._send_symbol_chart(chat_id, sym)
                else:
                    self.client.send_message("Usage: <code>/chart &lt;SYMBOL&gt;</code> (e.g. <code>/chart COMI</code>)", chat_id=chat_id, parse_mode="HTML")
                return {"action": "whitelisted_chart", "symbol": sym}

            elif cmd == "/regime":
                self._send_regime_info(chat_id)
                return {"action": "whitelisted_regime"}

            elif cmd == "/status":
                self._send_status_info(chat_id)
                return {"action": "whitelisted_status"}

            elif cmd in ("/help", "/start"):
                self._send_help_menu(chat_id, is_admin=is_admin_user)
                return {"action": "whitelisted_help"}

            # If user sent /pin while already whitelisted:
            elif cmd == "/pin":
                self.client.send_message("✅ Your terminal is already verified and active! Use /help for available commands.", chat_id=chat_id)
                return {"action": "already_whitelisted"}

        # ---------------------------------------------------------------------
        # 3. Unwhitelisted Users Flow (Permission-Slip & PIN Verification)
        # ---------------------------------------------------------------------
        if not is_user_whitelisted:
            entered_pin = ""
            if text.lower().startswith("/pin"):
                pin_parts = text.split()
                if len(pin_parts) >= 2:
                    entered_pin = pin_parts[1].strip()
            elif text and len(text) <= 30 and not text.startswith("/"):
                # Potential direct PIN entry
                entered_pin = text.strip()

            # Attempt PIN validation if an entry was made
            if entered_pin and self.store.validate_and_consume_pin(entered_pin, user_id):
                self.store.add_whitelisted(
                    chat_id=chat_id,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    pin=entered_pin,
                )

                welcome_msg = (
                    "✅ <b>Access Granted! Terminal Activated.</b>\n\n"
                    "Welcome to <b>Praecursor-EGX Institutional Intelligence</b>.\n"
                    "Your device is permanently verified. You will receive daily scan briefings.\n\n"
                    "<b>Commands:</b>\n"
                    "• /report - Latest daily market scan\n"
                    "• /top5 - Top 5 picks + technical radar charts\n"
                    "• /regime - Egyptian market regime\n"
                    "• /status - System diagnostics"
                )
                self.client.send_message(welcome_msg, chat_id=chat_id, parse_mode="HTML")

                # Notify Super Administrator
                if self.admin_chat_id:
                    uname_tag = f"@{username}" if username else "No username"
                    admin_notif = (
                        f"🎉 <b>User Verified:</b> {first_name} {last_name} ({uname_tag})\n"
                        f"ID: <code>{user_id}</code> entered PIN <b>{entered_pin}</b> and is now active."
                    )
                    self.client.send_message(admin_notif, chat_id=self.admin_chat_id, parse_mode="HTML")

                return {"action": "pin_verified", "user_id": user_id, "pin": entered_pin}

            elif text.lower().startswith("/pin"):
                self.client.send_message(
                    "❌ <b>Invalid or expired PIN code.</b>\nPlease check with the Administrator or wait for your approval slip.",
                    chat_id=chat_id,
                    parse_mode="HTML",
                )
                return {"action": "invalid_pin"}

            # Existing pending check
            pending = self.store.get_pending_by_user(user_id)
            if pending:
                self.client.send_message(
                    "🔒 <b>Access Pending.</b>\nYour request is awaiting Administrator PIN approval.\n"
                    "Once approved, you will receive your activation code here.",
                    chat_id=chat_id,
                    parse_mode="HTML",
                )
                return {"action": "already_pending"}

            # First-time visitor: generate Permission-Slip & Alert Administrator
            user_slip = (
                "🔒 <b>Praecursor-EGX Institutional Gateway</b>\n"
                "<i>Access Restricted.</i>\n\n"
                "Your access request has been submitted to the Administrator.\n"
                "Once approved, you will receive your invitation PIN code to activate your terminal."
            )
            self.client.send_message(user_slip, chat_id=chat_id, parse_mode="HTML")

            # Dispatch Permission-Slip Alert to Administrator
            if self.admin_chat_id:
                uname_tag = f"@{username}" if username else "None"
                timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                admin_alert = (
                    "🔔 <b>NEW ACCESS REQUEST</b>\n\n"
                    f"👤 <b>User:</b> {first_name} {last_name} ({uname_tag})\n"
                    f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                    f"🌐 <b>Language:</b> {language_code}\n"
                    f"🕒 <b>Time:</b> {timestamp_str}\n\n"
                    "💬 <b>To Approve:</b> Reply directly to this message with the PIN code for this person, or send:\n"
                    f"<code>/code {user_id} &lt;PIN&gt;</code>"
                )
                admin_resp = self.client.send_message(admin_alert, chat_id=self.admin_chat_id, parse_mode="HTML")
                admin_msg_id = admin_resp.get("result", {}).get("message_id", 0)

                self.store.record_pending_request(
                    user_id=user_id,
                    chat_id=chat_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                    admin_message_id=admin_msg_id,
                )

            return {"action": "access_requested", "user_id": user_id}

        return {"action": "unhandled"}

    # =========================================================================
    # Inbound Handlers (Whitelisted User Commands)
    # =========================================================================

    def _send_latest_report(self, chat_id: int) -> None:
        try:
            from praecursor.cli.telegram import load_latest_scan_result
            result = load_latest_scan_result()
        except Exception:
            result = None

        message = None
        dash_html = PROJECT_ROOT / "reports" / "dashboard.html"
        if dash_html.exists():
            try:
                message = self.formatter.format_from_dashboard_html(dash_html, top_n=5)
            except Exception:
                pass
        if not message and result:
            message = self.formatter.format_scanner_result(result, top_n=5)

        if message:
            self.client.send_message(message, chat_id=chat_id, parse_mode="HTML")
        else:
            self.client.send_message("⚠️ No scan report available in the system yet.", chat_id=chat_id)

    def _send_top5_with_charts(self, chat_id: int) -> None:
        try:
            from praecursor.cli.telegram import load_latest_scan_result
            result = load_latest_scan_result()
        except Exception:
            result = None

        if not result:
            self.client.send_message("⚠️ No scan report available yet.", chat_id=chat_id)
            return

        message = self.formatter.format_scanner_result(result, top_n=5)
        self.client.send_message(message, chat_id=chat_id, parse_mode="HTML")
        dispatch_candidate_charts(self.client, result=result, max_charts=5, verbose=False, chat_id=chat_id)

    def _send_symbol_chart(self, chat_id: int, symbol: str) -> None:
        sym = symbol.upper()
        chart_png = PROJECT_ROOT / "reports" / "charts" / f"{sym}_chart.png"
        if not chart_png.exists():
            try:
                from tools.chart_generator import render_chart_to_png
                res = render_chart_to_png(sym)
                if res and Path(res).exists():
                    chart_png = Path(res)
            except Exception:
                pass

        if chart_png.exists():
            caption = f"📊 Technical Candlestick Radar for <b>{sym}</b>"
            self.client.send_photo(chart_png, caption=caption, parse_mode="HTML", chat_id=chat_id)
        else:
            self.client.send_message(
                f"⚠️ Candlestick chart for <b>{sym}</b> not found. Available charts are produced during daily scans.",
                chat_id=chat_id,
                parse_mode="HTML",
            )

    def _send_regime_info(self, chat_id: int) -> None:
        dash_html = PROJECT_ROOT / "reports" / "dashboard.html"
        regime = "BULL TREND"
        if dash_html.exists():
            try:
                html = dash_html.read_text(encoding="utf-8", errors="replace")
                m = re.search(r'class="pill-val regime-[^>]*>([^<]+)</span>', html)
                if m:
                    regime = m.group(1).strip()
            except Exception:
                pass

        msg = (
            f"🏛️ <b>EGX Market Regime</b>: <b>{regime}</b>\n\n"
            "Calculated via EGX30 50-day and 200-day trend filters, market breadth index, "
            "and volatility dispersion models."
        )
        self.client.send_message(msg, chat_id=chat_id, parse_mode="HTML")

    def _send_status_info(self, chat_id: int) -> None:
        whitelisted_count = len(self.store.get_whitelisted_users())
        pending_count = len(self.store.list_pending_requests())

        scan_status_path = PROJECT_ROOT / "data" / "scan_status.json"
        stage_desc = "Idle"
        if scan_status_path.exists():
            try:
                import json
                with open(scan_status_path, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    stage_desc = st.get("stage_name", "Idle")
                    if st.get("running"):
                        stage_desc += f" (In progress: {st.get('percent', 0):.0f}%)"
            except Exception:
                pass

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = (
            "⚙️ <b>Praecursor-EGX Terminal Status</b>\n"
            "• Engine: Active & Long-Polling\n"
            f"• Whitelisted Terminals: <b>{whitelisted_count}</b>\n"
            f"• Pending Requests: <b>{pending_count}</b>\n"
            f"• Pipeline State: <i>{stage_desc}</i>\n"
            f"• Server Time: {now_utc}"
        )
        self.client.send_message(msg, chat_id=chat_id, parse_mode="HTML")

    def _send_help_menu(self, chat_id: int, is_admin: bool = False) -> None:
        lines = [
            "🏛️ <b>Praecursor-EGX Terminal Commands</b>\n",
            "<b>Market Intelligence:</b>",
            "• /report - Latest full daily scanner briefing",
            "• /top5 - Top 5 opportunity picks + radar charts",
            "• /chart &lt;SYM&gt; - Candlestick chart for symbol",
            "• /regime - Current EGX market regime status",
            "• /status - System diagnostics & pipeline health",
            "• /help - Display this command menu",
        ]
        if is_admin:
            lines.extend([
                "\n👑 <b>Administrator Control:</b>",
                "• <i>Reply directly to an access request alert with the PIN to approve.</i>",
                "• /pending - View all pending user access requests",
                "• /code &lt;user_id&gt; &lt;PIN&gt; - Assign PIN and approve user",
                "• /whitelist - List authorized terminals",
                "• /revoke &lt;user_id&gt; - Revoke terminal authorization",
                "• /setpin &lt;PIN&gt; [user_id] - Pre-create an invitation PIN",
                "• /broadcast &lt;message&gt; - Dispatch broadcast to all users",
            ])

        self.client.send_message("\n".join(lines), chat_id=chat_id, parse_mode="HTML")

    # =========================================================================
    # Long-Polling Loop
    # =========================================================================

    def poll_once(self) -> list[dict[str, Any]]:
        """Perform one long-polling cycle via getUpdates and process incoming updates."""
        offset = self.last_update_id + 1 if self.last_update_id > 0 else None
        res = self.client.get_updates(offset=offset, timeout=5)
        if not res.get("ok"):
            return []

        updates = res.get("result", [])
        events = []
        for upd in updates:
            upd_id = upd.get("update_id", 0)
            if upd_id > self.last_update_id:
                self.last_update_id = upd_id

            msg = upd.get("message") or upd.get("edited_message")
            if msg:
                ev = self.handle_message(msg)
                events.append(ev)

        return events

    def run_polling(self, poll_interval: float = 2.0, max_iterations: int | None = None) -> None:
        """Run long-polling daemon until interrupted."""
        print(f"[BotHub] Starting Telegram Bot Hub long-polling daemon (interval: {poll_interval}s)...")
        print(f"[BotHub] Super-Admin Chat ID: {self.admin_chat_id or 'Not Configured'}")
        print(f"[BotHub] Whitelisted terminals: {len(self.store.get_whitelisted_users())}")

        iterations = 0
        try:
            while True:
                if max_iterations is not None and iterations >= max_iterations:
                    break
                try:
                    self.poll_once()
                except Exception as e:
                    logger.warning(f"[BotHub] Error during poll cycle: {e}")

                iterations += 1
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n[BotHub] Long-polling daemon stopped by user (Ctrl+C).")
