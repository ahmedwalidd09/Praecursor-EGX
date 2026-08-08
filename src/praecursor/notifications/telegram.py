from dataclasses import dataclass
from pathlib import Path
import json
import os
import urllib.parse
import urllib.request
from typing import Any


@dataclass(frozen=True)
class TelegramSettings:
    """Telegram bot configuration loaded from environment variables."""

    bot_token: str
    chat_id: str

    @classmethod
    def from_environment(cls) -> "TelegramSettings":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        missing = []
        if not token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not chat_id:
            missing.append("TELEGRAM_CHAT_ID")

        if missing:
            raise RuntimeError("Missing environment variables: " + ", ".join(missing))

        return cls(bot_token=token, chat_id=chat_id)


class TelegramClient:
    """Small Telegram Bot API client using the Python standard library."""

    def __init__(self, settings: TelegramSettings):
        self.settings = settings
        self.base_url = f"https://api.telegram.org/bot{settings.bot_token}"

    def send_message(self, text: str, parse_mode: str | None = None) -> dict[str, Any]:
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
        return self._send_json_request(request)

    def send_document(self, file_path: Path, caption: str = "") -> dict[str, Any]:
        boundary = "----PraecursorEGXBoundary"
        file_bytes = file_path.read_bytes()
        body_parts = [
            self._form_field(boundary, "chat_id", self.settings.chat_id),
        ]

        if caption:
            body_parts.append(self._form_field(boundary, "caption", caption))

        body_parts.append(
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"document\"; filename=\"{file_path.name}\"\r\n"
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
            f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
            f"{value}\r\n"
        ).encode("utf-8")

    def _send_json_request(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram API error {error.code}: {body}") from error


class TelegramReportFormatter:
    """Format scanner results for Telegram messages."""

    def format_scanner_result(self, result: Any, top_n: int = 5) -> str:
        next_day = result.next_day_results[:top_n]
        swing = getattr(result, "swing_results", result.symbol_results)[:top_n] if hasattr(result, "swing_results") else []
        lines = [
            "📈 Praecursor-EGX Scan",
            f"Generated: {result.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"Symbols scanned: {result.success_count}",
            f"Failed: {result.error_count}",
            "",
            "🚀 Next-Day Candidates",
        ]
        lines.extend(self._format_candidate_rows(next_day))
        lines.extend(["", "🎯 Swing Candidates"])
        lines.extend(self._format_candidate_rows(swing))
        lines.extend(["", "Reports:", "- reports/dashboard.html", "- reports/next_day_candidates.csv"])
        return "\n".join(lines)

    def _format_candidate_rows(self, results: list[Any]) -> list[str]:
        if not results:
            return ["No candidates."]

        rows = []
        for rank, item in enumerate(results, start=1):
            score = item.next_day_score
            label = item.next_day_label
            rows.append(
                f"{rank}. {item.symbol} — {score:.0f}/100 — {label} — close {item.opportunity_score.latest_close:.2f}"
            )
        return rows
