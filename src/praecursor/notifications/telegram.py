from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import os
import sqlite3
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "telegram.json"
DASHBOARD_PATH = PROJECT_ROOT / "reports" / "dashboard.html"

FALLBACK_BOT_TOKEN = "8698596219:AAEl4jwnm3XeBzjwrx9jWBxnNpU7UpdFA3w"
FALLBACK_CHAT_ID = "8196296723"


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

    def send_message(self, text: str, parse_mode: str = "HTML", max_retries: int = 3) -> dict[str, Any]:
        if not self.settings.is_configured:
            logger.warning("Telegram bot credentials not configured.")
            return {"ok": False, "description": "Credentials not configured"}

        payload = {
            "chat_id": self.settings.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/sendMessage",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                return self._send_json_request(request)
            except Exception as e:
                last_error = e
                logger.warning(f"Telegram sendMessage attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    time.sleep(1.5 * attempt)

        raise RuntimeError(f"Telegram sendMessage failed after {max_retries} attempts: {last_error}")

    def send_document(self, file_path: Path, caption: str = "") -> dict[str, Any]:
        if not self.settings.is_configured:
            return {"ok": False, "description": "Credentials not configured"}

        boundary = "----PraecursorEGXBoundary"
        file_bytes = Path(file_path).read_bytes()
        body_parts = [
            self._form_field(boundary, "chat_id", self.settings.chat_id),
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


class TelegramReportFormatter:
    """Format scanner results for rich HTML Telegram messages."""

    def format_from_dashboard_html(self, dashboard_path: Path | str | None = None, top_n: int = 5) -> str | None:
        """Parse the generated dashboard HTML to guarantee 100% exact parity with the web dashboard."""
        target_path = Path(dashboard_path) if dashboard_path else DASHBOARD_PATH
        if not target_path.exists():
            if Path("reports/dashboard.html").exists():
                target_path = Path("reports/dashboard.html")
            else:
                return None

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            BeautifulSoup = None

        html = target_path.read_text(encoding="utf-8")

        reg_m = re.search(r'class="pill-val regime-[^>]*>([^<]+)</span>', html)
        regime = reg_m.group(1).strip() if reg_m else "BULL TREND"

        time_m = re.search(r'<span class="pill-label">LAST RAN AT:</span>\s*<span class="pill-val highlight">([^<]+)</span>', html)
        scan_time_str = time_m.group(1).strip() if time_m else datetime.now().strftime("%Y-%m-%d %I:%M %p Cairo")
        scan_time_str = scan_time_str.replace(" Cairo", "").strip()

        sess_m = re.search(r'<span class="pill-label">TARGET SESSION:</span>\s*<span class="pill-val highlight">([^<]+)</span>', html)
        target_session_raw = sess_m.group(1).strip() if sess_m else ""
        try:
            dt_sess = datetime.strptime(target_session_raw, "%Y-%m-%d")
            target_session_str = dt_sess.strftime("%A, %b %d, %Y")
        except Exception:
            target_session_str = target_session_raw or "Next Trading Session"

        blocks = []
        header = (
            f"🏛 <b>PRAECURSOR-EGX QUANT SCAN</b>\n"
            f"⚡ <b>Version:</b> v6.1 Institutional Alpha\n"
            f"🕒 <b>Last Ran At:</b> {scan_time_str}\n"
            f"🎯 <b>Predicted For:</b> {target_session_str} (Open)\n"
            f"🌐 <b>Market Regime:</b> {regime.title()}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        blocks.append(header)

        if not BeautifulSoup:
            return None

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".candidate-card")
        if not cards:
            return None

        count = 0
        for card in cards:
            sym_el = card.select_one(".symbol-name")
            comp_el = card.select_one(".company-name")
            badge_el = card.select_one(".card-type-badge")
            score_el = card.select_one(".hero-score-num")

            sym = sym_el.text.strip() if sym_el else ""
            comp = comp_el.text.strip() if comp_el else ""
            badge = badge_el.text.strip() if badge_el else ""

            if not sym or "Avoid" in badge:
                continue

            score_text = score_el.text.strip().replace("%", "") if score_el else "0"
            try:
                score = float(score_text)
            except ValueError:
                score = 0.0

            entry_val = 0.0
            target_val = 0.0
            target_pct = 0.0
            stop_val = 0.0
            stop_pct = 0.0

            for row in card.select(".level-row"):
                lbl = row.select_one(".level-label")
                val = row.select_one(".level-val")
                if not lbl or not val:
                    continue
                text_lbl = lbl.text.strip().upper()
                if "ENTRY" in text_lbl:
                    m = re.search(r"([\d\.]+)", val.text)
                    if m: entry_val = float(m.group(1))
                elif "TARGET" in text_lbl:
                    m = re.search(r"([\d\.]+)", val.text)
                    if m: target_val = float(m.group(1))
                    pct_el = row.select_one(".pct-chip")
                    if pct_el:
                        m_pct = re.search(r"([\d\.]+)", pct_el.text)
                        if m_pct: target_pct = float(m_pct.group(1))
                elif "STOP LOSS" in text_lbl:
                    m = re.search(r"([\d\.]+)", val.text)
                    if m: stop_val = float(m.group(1))
                    pct_el = row.select_one(".pct-chip")
                    if pct_el:
                        m_pct = re.search(r"([\d\.]+)", pct_el.text)
                        if m_pct: stop_pct = float(m_pct.group(1))

            rr_val = 1.5
            kelly_val = 22.0
            for s_item in card.select(".sizing-item"):
                lbl = s_item.select_one(".sizing-label")
                val = s_item.select_one(".sizing-val")
                if not lbl or not val:
                    continue
                text_lbl = lbl.text.strip().upper()
                if "R:R" in text_lbl:
                    m = re.search(r"([\d\.]+)", val.text)
                    if m: rr_val = float(m.group(1))
                elif "KELLY" in text_lbl:
                    m = re.search(r"([\d\.]+)", val.text)
                    if m: kelly_val = float(m.group(1))

            liq = "HIGH"
            card_text = card.get_text()
            if "MODERATE LIQUIDITY" in card_text:
                liq = "MODERATE"
            count += 1
            is_top = "Top Pick" in badge or count <= 2
            badge_title = f"⭐ <b>TOP PICK #{count}: {sym}</b>" if is_top else f"📌 <b>#{count}: {sym}</b>"
            comp_tag = f" ({comp})" if comp else ""

            def _fmt_p(val: float) -> str:
                if val <= 0:
                    return "0.00"
                if val < 0.10:
                    return f"{val:.4f}"
                elif val < 1.00:
                    return f"{val:.3f}"
                return f"{val:.2f}"

            card_lines = [
                f"{badge_title}{comp_tag}",
                f"• <b>AI Conviction:</b> {score:.1f}%",
                f"• <b>Entry:</b> {_fmt_p(entry_val)} EGP",
                f"• <b>Target:</b> {_fmt_p(target_val)} (+{target_pct:.1f}%)",
                f"• <b>Stop Loss:</b> {_fmt_p(stop_val)} (-{stop_pct:.1f}%)",
                f"• <b>R:R Ratio:</b> {rr_val:.2f}x | <b>Half-Kelly:</b> {kelly_val:.1f}%",
                f"• <b>Liquidity:</b> 💧 {liq}",
            ]
            blocks.append("\n".join(card_lines))

            if count >= top_n:
                break

        if not count:
            return None

        blocks.append("━━━━━━━━━━━━━━━━━━━━\n📊 <b>Full Terminal:</b> Open <code>reports/dashboard.html</code>")
        return "\n\n".join(blocks)

    def format_scanner_result(self, result: Any = None, top_n: int = 5) -> str:
        # 1. ALWAYS try parsing dashboard.html first for 100% exact parity with the UI
        dashboard_path = getattr(result, "dashboard_report_path", None) or DASHBOARD_PATH
        if not (dashboard_path and Path(dashboard_path).exists()):
            if Path("reports/dashboard.html").exists():
                dashboard_path = Path("reports/dashboard.html")

        if dashboard_path and Path(dashboard_path).exists():
            try:
                from_dash = self.format_from_dashboard_html(dashboard_path, top_n=top_n)
                if from_dash:
                    return from_dash
            except Exception as exc:
                logger.warning(f"Failed to format from dashboard HTML: {exc}")

        from praecursor.scoring.regime import MarketRegimeModel
        regime = MarketRegimeModel().get_latest_regime().get("regime", "Bull Trend")
        
        gen_dt = getattr(result, "generated_at", datetime.now()) if result is not None else datetime.now()
        if isinstance(gen_dt, str):
            try:
                gen_dt = datetime.fromisoformat(gen_dt.replace("Z", "+00:00"))
            except Exception:
                gen_dt = datetime.now()

        local_dt = _to_local_time(gen_dt)
        scan_time_str = local_dt.strftime("%Y-%m-%d %I:%M %p")
        target_session_str = get_next_egx_trading_day_str(local_dt)

        blocks = []
        header = (
            f"🏛 <b>PRAECURSOR-EGX QUANT SCAN</b>\n"
            f"⚡ <b>Version:</b> v6.1 Institutional Alpha\n"
            f"🕒 <b>Last Ran At:</b> {scan_time_str}\n"
            f"🎯 <b>Predicted For:</b> {target_session_str} (Open)\n"
            f"🌐 <b>Market Regime:</b> {regime}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        blocks.append(header)

        # Extract top next-day candidates
        raw_candidates = getattr(result, "next_day_results", [])
        top_candidates = []
        for item in raw_candidates:
            label = getattr(item, "next_day_label", "")
            if "Avoid" in label:
                continue
            top_candidates.append(item)
            if len(top_candidates) >= top_n:
                break

        if not top_candidates:
            blocks.append("⚠️ <b>No qualified breakout setups found today (Defensive Mode).</b>")
        else:
            for idx, item in enumerate(top_candidates, start=1):
                sym = getattr(item, "symbol", "")
                pred = getattr(item, "next_day_prediction", None)
                score = getattr(item, "next_day_score", 0.0)
                label = getattr(item, "next_day_label", "")
                reasons = getattr(item, "next_day_reasons", "") or getattr(item, "next_day_reasons_text", "")
                if isinstance(reasons, list):
                    reasons = " ; ".join(reasons)
                
                comp = ""
                opp_score = getattr(item, "opportunity_score", None)
                if opp_score:
                    comp = getattr(opp_score, "company", "")
                    latest_close = getattr(opp_score, "latest_close", 0.0)
                else:
                    latest_close = 0.0

                target_price = 0.0
                stop_loss = 0.0
                kelly = 0.15
                liq_tier = "HIGH"

                if pred:
                    latest_close = float(getattr(pred, "latest_close", latest_close))
                    target_price = float(getattr(pred, "target_price", 0.0))
                    stop_loss = float(getattr(pred, "stop_loss_price", 0.0))
                    kelly = float(getattr(pred, "kelly_fraction", 0.22))
                    liq_tier = getattr(pred, "liquidity_tier", "HIGH")
                else:
                    if target_price <= 0 and reasons:
                        m_tgt = re.search(r"Target placed at ([\d\.]+)", reasons)
                        if m_tgt:
                            target_price = float(m_tgt.group(1))
                        m_stp = re.search(r"Stop Loss placed at ([\d\.]+)", reasons)
                        if m_stp:
                            stop_loss = float(m_stp.group(1))
                        m_kly = re.search(r"Half-Kelly:\s*([\d\.]+)%", reasons)
                        if m_kly:
                            kelly = float(m_kly.group(1)) / 100.0

                    if target_price <= 0 and latest_close > 0:
                        target_price = latest_close * 1.07
                    if stop_loss <= 0 and latest_close > 0:
                        stop_loss = latest_close * 0.95

                t_pct = ((target_price - latest_close) / latest_close * 100) if latest_close > 0 else 0
                stop_pct = ((latest_close - stop_loss) / latest_close * 100) if latest_close > 0 else 0
                rr_ratio = (t_pct / stop_pct) if stop_pct > 0 else 0.0

                if not pred and t_pct > 0 and stop_pct > 0:
                    win_prob = max(0.40, min(0.50 + max(0.0, score - 50.0) * 0.005, 0.62))
                    b = (t_pct / 100.0) / (stop_pct / 100.0)
                    full_kelly = win_prob - ((1.0 - win_prob) / b)
                    half_kelly = full_kelly * 0.5
                    regime_mult = 1.2 if "Bull" in regime else 1.0
                    adjusted_kelly = half_kelly * regime_mult
                    kelly = max(0.05, min(adjusted_kelly, 0.25))

                if "Thin Liquidity" in reasons or "Slippage Risk" in reasons:
                    liq_tier = "THIN"
                elif "Moderate Liquidity" in reasons:
                    liq_tier = "MODERATE"
                elif "High Liquidity" in reasons:
                    liq_tier = "HIGH"

                is_top = "Top Pick" in label or idx <= 2
                badge = f"⭐ <b>TOP PICK #{idx}: {sym}</b>" if is_top else f"📌 <b>#{idx}: {sym}</b>"
                comp_tag = f" ({comp})" if comp else ""

                card = [
                    f"{badge}{comp_tag}",
                    f"• <b>AI Conviction:</b> {score:.1f}%",
                    f"• <b>Entry:</b> {latest_close:.2f} EGP",
                    f"• <b>Target:</b> {target_price:.2f} (+{t_pct:.1f}%)",
                    f"• <b>Stop Loss:</b> {stop_loss:.2f} (-{stop_pct:.1f}%)",
                    f"• <b>R:R Ratio:</b> {rr_ratio:.2f}x | <b>Half-Kelly:</b> {kelly*100:.1f}%",
                    f"• <b>Liquidity:</b> 💧 {liq_tier}",
                ]
                blocks.append("\n".join(card))

        blocks.append("━━━━━━━━━━━━━━━━━━━━\n📊 <b>Full Terminal:</b> Open <code>reports/dashboard.html</code>")
        return "\n\n".join(blocks)


def dispatch_telegram_scan_briefing(result=None, top_n: int = 5, verbose: bool = True) -> bool:
    """Send latest scan report to Telegram bot."""
    settings = TelegramSettings.load()
    if not settings.is_configured:
        if verbose:
            print("[Telegram] Bot credentials not configured in config/telegram.json or ENV. Skipping Telegram dispatch.")
        return False

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
            return True
        else:
            if verbose:
                print(f"[Telegram] [FAILED] Telegram API response: {resp}")
            return False
    except Exception as e:
        if verbose:
            print(f"[Telegram] [ERROR] Delivery failed: {e}")
        return False
