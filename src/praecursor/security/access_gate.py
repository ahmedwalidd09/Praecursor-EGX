"""Telegram Access Gate & Machine Whitelisting for Praecursor-EGX.

Implements cryptographically signed machine-fingerprint licensing (HMAC-SHA256)
and Telegram-based on-demand permission slips.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import socket
import sys
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SECRET_SALT = b"PRAECURSOR_EGX_EXCLUSIVE_INSTITUTIONAL_2026_HMAC_KEY"
WHITELIST_FILE = PROJECT_ROOT / "data" / "whitelist.lic"


def get_machine_fingerprint() -> str:
    """Retrieve stable unique hardware GUID from Windows Registry or SHA256 fallback."""
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if guid:
                return str(guid).strip()
        except Exception:
            pass
    # Fallback to hostname and username hash
    fallback = f"{socket.gethostname()}-{os.environ.get('USERNAME', 'user')}"
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


def get_short_node_id() -> str:
    """Derive short, readable Node identifier (e.g., NODE-4E8A)."""
    fp = get_machine_fingerprint()
    digest = hashlib.sha256(fp.encode("utf-8")).hexdigest()[:6].upper()
    return f"NODE-{digest}"


def is_machine_whitelisted() -> bool:
    """Check if current machine has a valid cryptographic whitelist license."""
    if not WHITELIST_FILE.exists():
        return False
    try:
        content = WHITELIST_FILE.read_text(encoding="utf-8").strip()
        data = json.loads(content)
        stored_signature = data.get("signature", "")
        fp = get_machine_fingerprint()
        expected = hmac.new(SECRET_SALT, fp.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(stored_signature, expected)
    except Exception:
        return False


def whitelist_current_machine(approved_pin: str = "") -> bool:
    """Permanently whitelist this machine by generating a signed license file."""
    try:
        fp = get_machine_fingerprint()
        signature = hmac.new(SECRET_SALT, fp.encode("utf-8"), hashlib.sha256).hexdigest()
        data = {
            "node_id": get_short_node_id(),
            "signature": signature,
            "pin": approved_pin,
            "whitelisted_at": datetime.now(timezone.utc).isoformat(),
        }
        WHITELIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        WHITELIST_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning(f"Failed to write whitelist license: {e}")
        return False


def get_telegram_credentials() -> tuple[str, str]:
    """Retrieve Telegram Bot Token and Admin Chat ID from TelegramSettings or environment."""
    try:
        from praecursor.notifications.telegram import TelegramSettings

        settings = TelegramSettings.load()
        bot_token = settings.bot_token.strip()
        chat_id = str(settings.chat_id).strip()
        if bot_token and chat_id:
            return bot_token, chat_id
    except Exception:
        pass

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return bot_token, chat_id


def send_telegram_access_request(
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> tuple[bool, str]:
    """Send access request notification to admin's Telegram chat."""
    if not bot_token or not chat_id:
        cfg_token, cfg_chat_id = get_telegram_credentials()
        bot_token = bot_token or cfg_token
        chat_id = chat_id or cfg_chat_id

    if not bot_token or not chat_id:
        return False, "Telegram Bot Token or Chat ID is not configured."

    node_id = get_short_node_id()
    hostname = socket.gethostname()
    username = os.environ.get("USERNAME", "Unknown")

    message_text = (
        f"🔒 <b>[Praecursor-EGX] Access Request</b>\n\n"
        f"<b>Node ID:</b> <code>{node_id}</code>\n"
        f"<b>Host:</b> {hostname}\n"
        f"<b>User:</b> {username}\n"
        f"<b>Platform:</b> Windows x64\n\n"
        f"👉 <b>To grant access:</b> Reply with:\n"
        f"<code>/approve {node_id} &lt;PIN&gt;</code>\n"
        f"<i>(Example: /approve {node_id} 8492)</i>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": str(chat_id),
        "text": message_text,
        "parse_mode": "HTML",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return True, "Access request dispatched to Telegram."
            return False, data.get("description", "Unknown Telegram API error.")
    except Exception as e:
        return False, f"Network error sending Telegram request: {e}"


def check_telegram_approval(
    entered_pin: str = "",
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> tuple[bool, str]:
    """
    Poll recent Telegram updates from the authorized chat_id for approval of this Node ID.
    Supports either explicit entered PIN matching or auto-approving if admin replied with PIN.
    """
    if not bot_token or not chat_id:
        cfg_token, cfg_chat_id = get_telegram_credentials()
        bot_token = bot_token or cfg_token
        chat_id = chat_id or cfg_chat_id

    if not bot_token or not chat_id:
        return False, "Telegram credentials missing."

    node_id = get_short_node_id().upper()
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset=-25"

    try:
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                return False, data.get("description", "Error fetching bot updates.")

            updates = data.get("result", [])
            for u in reversed(updates):
                msg = u.get("message", {}) or u.get("edited_message", {})
                msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                if msg_chat_id != str(chat_id):
                    continue

                text = msg.get("text", "").strip()
                # Check for /approve NODE-XXXX <PIN> or /grant NODE-XXXX <PIN>
                parts = text.split()
                if len(parts) >= 3 and parts[0].lower() in ("/approve", "/grant"):
                    target_node = parts[1].strip().upper()
                    target_pin = parts[2].strip()

                    if target_node == node_id:
                        if entered_pin:
                            if entered_pin.strip() == target_pin:
                                whitelist_current_machine(entered_pin.strip())
                                return True, "PIN verified! Terminal whitelisted permanently."
                            else:
                                return False, "Entered PIN does not match admin's approved code."
                        else:
                            # Auto-approval without retyping
                            whitelist_current_machine(target_pin)
                            return True, f"Admin approved code {target_pin}! Terminal whitelisted permanently."

            if entered_pin:
                return False, f"No approval found in Telegram for {node_id}. Ensure you replied '/approve {node_id} {entered_pin}'."
            return False, f"Waiting for admin approval in Telegram for {node_id}..."
    except Exception as e:
        return False, f"Failed checking Telegram updates: {e}"
