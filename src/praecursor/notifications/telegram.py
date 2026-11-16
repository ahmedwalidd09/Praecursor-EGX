from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from typing import Any

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure") and stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "telegram.json"
DASHBOARD_PATH = PROJECT_ROOT / "reports" / "dashboard.html"

FALLBACK_BOT_TOKEN = ""
FALLBACK_CHAT_ID = ""


@dataclass(frozen=True)
class TelegramSettings:
    """Telegram bot configuration loaded from config file or environment variables."""

    bot_token: str
    chat_id: str

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> "TelegramSettings":
        token = ""
        chat_id = ""

        candidate_paths = []
        if config_path:
            candidate_paths.append(Path(config_path))
        candidate_paths.extend([
            CONFIG_PATH,
            PROJECT_ROOT / "config" / "telegram.json",
            Path("config/telegram.json"),
        ])

        for p in candidate_paths:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    token = data.get("bot_token", "")
                    chat_id = str(data.get("chat_id", ""))
                    if token and chat_id:
                        break
                except Exception as e:
                    logger.warning(f"Failed to read {p}: {e}")

        if not token:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not chat_id:
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        # Fallback to configured bot credentials if not found
        if not token:
            token = FALLBACK_BOT_TOKEN
        if not chat_id:
            chat_id = FALLBACK_CHAT_ID

        # Ensure config file is persisted
        settings = cls(bot_token=token.strip(), chat_id=str(chat_id).strip())
        if settings.is_configured and not CONFIG_PATH.exists():
            try:
                settings.save(CONFIG_PATH)
            except Exception:
                pass

        return settings

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def save(self, config_path: Path | None = None) -> None:
        target = Path(config_path) if config_path else CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
        }
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def from_environment(cls) -> "TelegramSettings":
        settings = cls.load()
        if not settings.is_configured:
            raise RuntimeError(
                "Missing Telegram credentials. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                "or configure config/telegram.json"
            )
        return settings


import time


class TelegramClient:
    """Small Telegram Bot API client using standard library with automatic retry."""

    def __init__(self, settings: TelegramSettings | None = None):
        self.settings = settings or TelegramSettings.load()
        self.base_url = f"https://api.telegram.org/bot{self.settings.bot_token}"

    @staticmethod
    def split_message(text: str, max_length: int = 4000) -> list[str]:
        """Split a message into chunks within Telegram's 4096 character limit."""
        if not text or len(text) <= max_length:
            return [text] if text else [""]

        chunks = []
        lines = text.split("\n")
        current_chunk: list[str] = []
        current_len = 0

        for line in lines:
            if len(line) > max_length:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_len = 0
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
                continue

            line_len = len(line) + (1 if current_chunk else 0)
            if current_len + line_len > max_length:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = len(line)
            else:
                current_chunk.append(line)
                current_len += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def send_message(
        self,
        text: str,
        chat_id: str | int | None = None,
        parse_mode: str = "HTML",
        reply_to_message_id: int | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        if not self.settings.is_configured:
            logger.warning("Telegram bot credentials not configured.")
            return {"ok": False, "description": "Credentials not configured"}

        target_chat_id = str(chat_id) if chat_id is not None else self.settings.chat_id
        chunks = self.split_message(text, max_length=4000)
        last_resp = {"ok": True}
        for chunk in chunks:
            payload = {
                "chat_id": target_chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            if reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id
            if parse_mode:
                payload["parse_mode"] = parse_mode

            data = urllib.parse.urlencode(payload).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/sendMessage",
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            sent = False
            for attempt in range(1, max_retries + 1):
                try:
                    last_resp = self._send_json_request(request)
                    sent = True
                    break
                except Exception as e:
                    # If HTML parsing failed on a chunk, retry without parse_mode (plain text)
                    if "can't parse entities" in str(e).lower() and parse_mode:
                        try:
                            payload_plain = dict(payload)
                            payload_plain.pop("parse_mode", None)
                            data_plain = urllib.parse.urlencode(payload_plain).encode("utf-8")
                            req_plain = urllib.request.Request(
                                f"{self.base_url}/sendMessage",
                                data=data_plain,
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                            )
                            last_resp = self._send_json_request(req_plain)
                            sent = True
                            break
                        except Exception:
                            pass
                    logger.warning("Telegram sendMessage attempt %s/%s failed", attempt, max_retries)
                    if attempt < max_retries:
                        time.sleep(1.5 * attempt)

            if not sent:
                raise RuntimeError(f"Telegram sendMessage failed after {max_retries} attempts") from None

        return last_resp

    def send_document(
        self,
        file_path: Path,
        caption: str = "",
        chat_id: str | int | None = None,
    ) -> dict[str, Any]:
        if not self.settings.is_configured:
            return {"ok": False, "description": "Credentials not configured"}

        target_chat_id = str(chat_id) if chat_id is not None else self.settings.chat_id
        boundary = "----PraecursorEGXBoundary"
        file_bytes = Path(file_path).read_bytes()
        body_parts = [
            self._form_field(boundary, "chat_id", target_chat_id),
        ]

        if caption:
            body_parts.append(self._form_field(boundary, "caption", caption))

        body_parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="document"; filename="{Path(file_path).name}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode("utf-8")
            + file_bytes
            + b"\r\n"
        )
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(body_parts)

        request = urllib.request.Request(
            f"{self.base_url}/sendDocument",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        return self._send_json_request(request)

    def send_photo(
        self,
        photo_path: Path,
        caption: str = "",
        parse_mode: str = "HTML",
        chat_id: str | int | None = None,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        """Send a photo image to Telegram with optional caption and HTML formatting."""
        if not self.settings.is_configured:
            return {"ok": False, "description": "Credentials not configured"}

        p = Path(photo_path)
        if not p.exists() or not p.is_file():
            return {"ok": False, "description": f"Photo not found: {p}"}

        target_chat_id = str(chat_id) if chat_id is not None else self.settings.chat_id
        boundary = "----PraecursorEGXPhotoBoundary"
        file_bytes = p.read_bytes()
        filename = p.name
        content_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

        body_parts = [
            self._form_field(boundary, "chat_id", target_chat_id),
        ]

        if reply_to_message_id is not None:
            body_parts.append(self._form_field(boundary, "reply_to_message_id", str(reply_to_message_id)))

        if caption:
            # Telegram photo caption limit is 1024 characters
            body_parts.append(self._form_field(boundary, "caption", caption[:1024]))
            if parse_mode:
                body_parts.append(self._form_field(boundary, "parse_mode", parse_mode))

        body_parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
            + file_bytes
            + b"\r\n"
        )
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(body_parts)

        request = urllib.request.Request(
            f"{self.base_url}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        return self._send_json_request(request)

    def get_updates(self, offset: int | None = None, timeout: int = 10, limit: int = 100) -> dict[str, Any]:
        """Fetch incoming bot updates via long polling."""
        if not self.settings.is_configured:
            return {"ok": False, "result": []}

        params: dict[str, Any] = {"timeout": timeout, "limit": limit}
        if offset is not None:
            params["offset"] = offset

        query_str = urllib.parse.urlencode(params)
        request = urllib.request.Request(f"{self.base_url}/getUpdates?{query_str}")
        try:
            return self._send_json_request(request)
        except Exception as e:
            logger.warning(f"Telegram getUpdates failed: {e}")
            return {"ok": False, "result": [], "error": str(e)}

    def _form_field(self, boundary: str, name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")

    def _send_json_request(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram API error {error.code}: {body}") from error


def get_next_egx_trading_day_str(from_date: datetime | None = None) -> str:
    dt = from_date or datetime.now()
    cur = dt.date() if hasattr(dt, "date") else dt
    from datetime import timedelta
    nxt = cur + timedelta(days=1)
    while nxt.weekday() in (4, 5):
        nxt += timedelta(days=1)
    return nxt.strftime("%A, %b %d, %Y")


import re


def _to_local_time(dt: datetime) -> datetime:
    """Convert UTC datetime to local system datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


import html as html_lib


from praecursor.scoring.price_plan import price_text


class TelegramReportFormatter:
    """Format scanner results for rich HTML Telegram messages."""

    def format_snapshot(self, saved, top_n=5):
        lines = ["<b>PRAECURSOR-EGX · Daily research shortlist</b>",
                 "For session: " + html_lib.escape(str(saved.get("target_session") or "Not recorded")),
                 "Price session: " + html_lib.escape(str(saved.get("price_session") or "Not recorded")),
                 "Technical scores are not success probabilities."]
        signals = sorted((r for r in saved.get("signals", []) if r.get("candidate_rank")),
                         key=lambda r: r["candidate_rank"])[:top_n]
        paper = saved.get("paper") or {}
        decisions = {o["symbol"]: o for o in paper.get("orders", [])} if paper.get("session") == saved.get("target_session") else {}
        for row in signals:
            lines.append(f"\n<b>#{row['candidate_rank']} {html_lib.escape(row['symbol'])}</b> · Score {row['next_day_score']:.1f}/100")
            currency = (row.get("shortlist") or {}).get("currency")
            lines.append("Close / target / stop" + (f" ({html_lib.escape(currency)})" if currency else "") + ": " + " / ".join(
                price_text(row.get(k)) for k in ("latest_close", "next_day_target", "next_day_stop_loss")))
            plan = (row.get("plans") or {}).get("next_day")
            if plan and plan["status"] == "heuristic-active":
                lines.append(f"Reference R/R {plan['gross_reward_risk']:.2f}× gross · "
                             f"{plan['net_reward_risk']:.2f}× at {plan['scenario_cost_bps']:g} bps · "
                             + html_lib.escape(plan["policy"]))
            for reason in row.get("selection_reasons", []):
                lines.append("• " + html_lib.escape(reason))
            lines.append(html_lib.escape(row.get("source_status") or "Source confirmation unavailable"))
            decision = decisions.get(row["symbol"])
            if decision:
                detail = (f"Paper eligible: {decision['quantity']} hypothetical shares" if decision["decision"] == "paper_eligible"
                          else "Watch only: " + "; ".join(decision.get("reasons", []))[:160])
                lines.append(html_lib.escape(detail))
            if row.get("next_day_probability") is not None:
                lines.append(f"Validated target-touch probability: {row['next_day_probability']:.1%}")
        if len(signals) < top_n:
            currency_gate = "quote currency, " if saved.get("shortlist_policy") else ""
            lines.append(f"\nOnly {len(signals)}/{top_n} candidates passed {currency_gate}price, history, liquidity and plan checks.")
        return "\n".join(lines)

    def format_from_dashboard_html(self, dashboard_path: Path | str | None = None, top_n: int = 5) -> str | None:
        """Parse the generated dashboard HTML to guarantee 100% exact parity with the web dashboard."""
        target_path = Path(dashboard_path) if dashboard_path else DASHBOARD_PATH
        if not target_path.exists():
            if Path("reports/dashboard.html").exists():
                target_path = Path("reports/dashboard.html")
            else:
                return None

        try:
            html = target_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Could not read dashboard HTML from %s: %s", target_path, exc)
            return None

        snapshot = re.search(r'<script id="saved-snapshot" type="application/json">(.*?)</script>', html, re.S)
        return self.format_snapshot(json.loads(snapshot.group(1)), top_n) if snapshot else None

    def format_scanner_result(self, result: Any = None, top_n: int = 5) -> str:
        dashboard_path = getattr(result, "dashboard_report_path", None)
        if dashboard_path or result is None:
            try:
                snapshot = self.format_from_dashboard_html(dashboard_path, top_n)
                if snapshot:
                    return snapshot
            except (ValueError, TypeError) as exc:
                logger.warning("Could not read saved dashboard snapshot: %s", exc)

        from datetime import date
        from praecursor.core.sessions import next_session
        items = getattr(result, "next_day_results", ()) or ()
        rows = []
        shortlist_policy = None
        for item in items:
            shortlist = getattr(item, "shortlist", None)
            if shortlist:
                shortlist_policy = shortlist.get("policy")
            rank = getattr(item, "candidate_rank", None)
            if not rank:
                continue
            prediction = item.next_day_prediction
            rows.append(dict(symbol=item.symbol, candidate_rank=rank,
                next_day_score=item.next_day_score, latest_close=prediction.latest_close,
                next_day_target=prediction.target_price, next_day_stop_loss=prediction.stop_loss_price,
                selection_reasons=item.selection_reasons, source_status=item.source_status, shortlist=shortlist,
                next_day_probability=prediction.probability, plans=dict(next_day=prediction.plan)))
        price_session = getattr(result, "end_date", None)
        if isinstance(price_session, str):
            price_session = date.fromisoformat(price_session)
        return self.format_snapshot(dict(signals=rows, price_session=price_session,
            target_session=next_session(price_session) if price_session else None,
            shortlist_policy=shortlist_policy), top_n)


def dispatch_candidate_charts(
    client: TelegramClient,
    result=None,
    max_charts: int = 5,
    verbose: bool = True,
    chat_id: str | int | None = None,
) -> int:
    """Dispatch high-resolution chart photos for the top actionable candidates to Telegram."""
    sent_count = 0

    if result is None:
        try:
            from praecursor.cli.telegram import load_latest_scan_result
            result = load_latest_scan_result()
        except Exception:
            result = None

    if not result:
        return 0

    candidates = getattr(result, "next_day_results", [])
    if not candidates:
        return 0

    # Filter out Avoid candidates
    actionable = [c for c in candidates if getattr(c, "candidate_rank", None)]
    
    # Sort by next_day_score descending
    actionable.sort(key=lambda x: x.candidate_rank)

    target_cid = str(chat_id) if chat_id is not None else client.settings.chat_id

    for rank, item in enumerate(actionable[:max_charts], start=1):
        sym = getattr(item, "symbol", "")
        if not sym:
            continue
        try:
            from tools.chart_generator import render_chart_to_png
            chart_png = render_chart_to_png(sym)
        except Exception:
            chart_png = None

        if not chart_png or not Path(chart_png).exists():
            continue

        pred = getattr(item, "next_day_prediction", None)
        opp = getattr(item, "opportunity_score", None)
        company = getattr(opp, "company", sym) if opp else sym
        target, stop = getattr(pred, "target_price", None), getattr(pred, "stop_loss_price", None)
        currency = (getattr(item, "shortlist", None) or {}).get("currency")
        caption = (
            f"<b>#{rank} {html_lib.escape(sym)} · {html_lib.escape(company)}</b>\n"
            f"Target / stop: {price_text(target)} / {price_text(stop)}"
            + (f" {html_lib.escape(currency)}" if currency else "")
        )

        try:
            if verbose:
                print(f"[Telegram] Sending technical radar chart for {sym} to Chat ID {target_cid}...")
            resp = client.send_photo(Path(chart_png), caption=caption, parse_mode="HTML", chat_id=target_cid)
            if resp.get("ok"):
                sent_count += 1
                if verbose:
                    print(f"[Telegram] [SUCCESS] Chart for {sym} delivered!")
            else:
                if verbose:
                    print(f"[Telegram] Warning: Failed to send chart for {sym}: {resp}")
        except Exception as e:
            if verbose:
                print(f"[Telegram] Warning: Error sending photo for {sym}: {e}")

    return sent_count


def dispatch_telegram_scan_briefing(result=None, top_n: int = 5, verbose: bool = True, send_charts: bool = True) -> bool:
    """Send latest scan report and top candidate chart photos to Telegram bot and whitelisted terminals."""
    settings = TelegramSettings.load()
    if not settings.is_configured:
        if verbose:
            print("[Telegram] Bot credentials not configured in config/telegram.json or ENV. Skipping Telegram dispatch.")
        return False

    try:
        from praecursor.notifications.bot_hub import TelegramBotHub
        hub = TelegramBotHub(settings=settings)
        res = hub.broadcast_scan_briefing(run_result=result, top_n=top_n, send_charts=send_charts, verbose=verbose)
        return bool(res.get("ok"))
    except Exception as e:
        if verbose:
            print(f"[Telegram] BotHub broadcast fallback: {e}")

    client = TelegramClient(settings)
    formatter = TelegramReportFormatter()

    if result is None:
        from praecursor.cli.telegram import load_latest_scan_result
        result = load_latest_scan_result()

    if result is None:
        if verbose:
            print("[Telegram] No scan result available to dispatch.")
        return False

    message = formatter.format_scanner_result(result, top_n=top_n)
    try:
        if verbose:
            print(f"[Telegram] Dispatching live scan report to Chat ID {settings.chat_id}...")
        resp = client.send_message(message, parse_mode="HTML")
        if resp.get("ok"):
            if verbose:
                print(f"[Telegram] [SUCCESS] Scan report delivered to Chat ID {settings.chat_id}!")
            if send_charts:
                dispatch_candidate_charts(client, result=result, max_charts=5, verbose=verbose)
            return True
        else:
            if verbose:
                print(f"[Telegram] [FAILED] Telegram API response: {resp}")
            return False
    except Exception as e:
        if verbose:
            print(f"[Telegram] [ERROR] Delivery failed: {e}")
        return False
