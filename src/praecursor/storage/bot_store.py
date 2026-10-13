from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any

from praecursor.storage.database import connect, DATABASE

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JSON_PATH = PROJECT_ROOT / "data" / "bot_whitelist.json"

BOT_STORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_whitelisted_users (
    chat_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    pin_used TEXT,
    approved_at TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_whitelisted_user_id
ON bot_whitelisted_users (user_id);

CREATE TABLE IF NOT EXISTS bot_pending_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    chat_id INTEGER,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT,
    requested_at TEXT,
    status TEXT DEFAULT 'PENDING',
    assigned_pin TEXT,
    admin_message_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_pending_admin_msg
ON bot_pending_requests (admin_message_id);

CREATE TABLE IF NOT EXISTS bot_pins (
    pin_code TEXT PRIMARY KEY,
    user_id INTEGER,
    created_at TEXT,
    is_used INTEGER DEFAULT 0,
    used_at TEXT
);
"""


class BotAccessStore:
    """Access management and permission store for the Praecursor Telegram bot hub."""

    def __init__(self, database_path: Path | str | None = None, json_path: Path | str | None = None):
        self.database_path = Path(database_path) if database_path else DATABASE
        self.json_path = Path(json_path) if json_path else DEFAULT_JSON_PATH
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def initialize(self) -> None:
        """Create required tables and sync initial json state if needed."""
        with closing(self._connect()) as conn:
            conn.executescript(BOT_STORE_SCHEMA)

        # Synchronize from existing JSON mirror if database table is empty
        try:
            with closing(self._connect()) as conn:
                count = conn.execute("SELECT COUNT(*) FROM bot_whitelisted_users").fetchone()[0]
                if count == 0 and self.json_path.exists():
                    self._import_from_json()
        except Exception as e:
            logger.debug(f"JSON mirror initial import skipped: {e}")

    def is_whitelisted(self, chat_id: int) -> bool:
        """Check if chat_id or user_id has active authorization."""
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT 1 FROM bot_whitelisted_users WHERE (chat_id = ? OR user_id = ?) AND is_active = 1 LIMIT 1",
                    (chat_id, chat_id),
                ).fetchone()
                if row:
                    return True
        except Exception as e:
            logger.warning(f"Error checking whitelist database: {e}")

        return self._check_json_whitelist(chat_id)

    def add_whitelisted(
        self,
        chat_id: int,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        pin: str = "",
    ) -> bool:
        """Authorize a user terminal permanently into the whitelist."""
        now_str = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                """INSERT INTO bot_whitelisted_users 
                   (chat_id, user_id, username, first_name, last_name, pin_used, approved_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                   ON CONFLICT(chat_id) DO UPDATE SET
                       user_id = excluded.user_id,
                       username = excluded.username,
                       first_name = excluded.first_name,
                       last_name = excluded.last_name,
                       pin_used = excluded.pin_used,
                       approved_at = excluded.approved_at,
                       is_active = 1""",
                (chat_id, user_id, username, first_name, last_name, pin, now_str),
            )
            conn.execute(
                "UPDATE bot_pending_requests SET status = 'APPROVED' WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()

        self._sync_to_json()
        return True

    def remove_whitelisted(self, user_id: int) -> bool:
        """Revoke user authorization."""
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "UPDATE bot_whitelisted_users SET is_active = 0 WHERE user_id = ? OR chat_id = ?",
                (user_id, user_id),
            )
            conn.commit()
            revoked = cursor.rowcount > 0

        self._sync_to_json()
        return revoked

    def get_whitelisted_users(self) -> list[dict[str, Any]]:
        """Retrieve all active whitelisted user records."""
        try:
            with closing(self._connect()) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM bot_whitelisted_users WHERE is_active = 1 ORDER BY approved_at ASC"
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"Error reading whitelist database: {e}")
            return self._read_json_whitelist()

    def record_pending_request(
        self,
        user_id: int,
        chat_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        language_code: str = "",
        admin_message_id: int = 0,
    ) -> int:
        """Insert or refresh a pending access request for a new user."""
        now_str = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id FROM bot_pending_requests WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row:
                req_id = row[0]
                conn.execute(
                    """UPDATE bot_pending_requests
                       SET chat_id = ?, username = ?, first_name = ?, last_name = ?,
                           language_code = ?, requested_at = ?, status = 'PENDING',
                           admin_message_id = ?
                       WHERE id = ?""",
                    (chat_id, username, first_name, last_name, language_code, now_str, admin_message_id, req_id),
                )
                conn.commit()
                return req_id
            else:
                cursor = conn.execute(
                    """INSERT INTO bot_pending_requests
                       (user_id, chat_id, username, first_name, last_name, language_code, requested_at, status, admin_message_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)""",
                    (user_id, chat_id, username, first_name, last_name, language_code, now_str, admin_message_id),
                )
                conn.commit()
                return cursor.lastrowid

    def get_pending_by_user(self, user_id: int) -> dict[str, Any] | None:
        """Retrieve pending request details by user ID."""
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bot_pending_requests WHERE user_id = ? AND status = 'PENDING'",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_pending_by_admin_message_id(self, msg_id: int) -> dict[str, Any] | None:
        """Find pending request by the administrator alert message ID (for Reply-to-Approve flow)."""
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bot_pending_requests WHERE admin_message_id = ? AND status = 'PENDING'",
                (msg_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_pending_requests(self) -> list[dict[str, Any]]:
        """List all unapproved user requests in the queue."""
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM bot_pending_requests WHERE status = 'PENDING' ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def assign_pin_to_request(self, user_id: int, pin: str) -> bool:
        """Assign an approval PIN code to a pending request and register it in bot_pins."""
        clean_pin = pin.strip().upper()
        now_str = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE bot_pending_requests SET assigned_pin = ? WHERE user_id = ? AND status = 'PENDING'",
                (clean_pin, user_id),
            )
            conn.execute(
                """INSERT INTO bot_pins (pin_code, user_id, created_at, is_used, used_at)
                   VALUES (?, ?, ?, 0, NULL)
                   ON CONFLICT(pin_code) DO UPDATE SET user_id=excluded.user_id, is_used=0, used_at=NULL""",
                (clean_pin, user_id, now_str),
            )
            conn.commit()
            return True

    def create_pin(self, pin_code: str, user_id: int | None = None) -> bool:
        """Pre-create a PIN code directly."""
        clean_pin = pin_code.strip().upper()
        now_str = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                """INSERT INTO bot_pins (pin_code, user_id, created_at, is_used, used_at)
                   VALUES (?, ?, ?, 0, NULL)
                   ON CONFLICT(pin_code) DO UPDATE SET user_id=excluded.user_id, is_used=0, used_at=NULL""",
                (clean_pin, user_id, now_str),
            )
            conn.commit()
            return True

    def validate_and_consume_pin(self, pin: str, user_id: int) -> bool:
        """Validate if the PIN is unused and assigned to the user (or unassigned), and consume it."""
        clean_pin = pin.strip().upper()
        now_str = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM bot_pins WHERE UPPER(pin_code) = ? AND is_used = 0",
                (clean_pin,),
            ).fetchone()
            if not row:
                return False

            pin_user_id = row["user_id"]
            if pin_user_id is not None and pin_user_id != 0 and pin_user_id != user_id:
                return False

            conn.execute(
                "UPDATE bot_pins SET is_used = 1, used_at = ?, user_id = ? WHERE pin_code = ?",
                (now_str, user_id, row["pin_code"]),
            )
            conn.execute(
                "UPDATE bot_pending_requests SET status = 'APPROVED' WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            return True

    def _sync_to_json(self) -> None:
        """Mirror current active whitelisted records to bot_whitelist.json."""
        try:
            users = self.get_whitelisted_users()
            self.json_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.json_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self.json_path)
        except Exception as e:
            logger.warning(f"Failed to sync whitelist to JSON: {e}")

    def _import_from_json(self) -> None:
        """Import whitelisted users from JSON into database."""
        if not self.json_path.exists():
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    chat_id = item.get("chat_id")
                    if chat_id:
                        self.add_whitelisted(
                            chat_id=int(chat_id),
                            user_id=int(item.get("user_id", chat_id)),
                            username=str(item.get("username", "")),
                            first_name=str(item.get("first_name", "")),
                            last_name=str(item.get("last_name", "")),
                            pin=str(item.get("pin_used", "")),
                        )
        except Exception as e:
            logger.warning(f"Error importing whitelist from JSON: {e}")

    def _read_json_whitelist(self) -> list[dict[str, Any]]:
        if not self.json_path.exists():
            return []
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [d for d in data if d.get("is_active", 1)]
        except Exception:
            pass
        return []

    def _check_json_whitelist(self, chat_id: int) -> bool:
        users = self._read_json_whitelist()
        for u in users:
            if u.get("chat_id") == chat_id or u.get("user_id") == chat_id:
                return bool(u.get("is_active", 1))
        return False


# Module-level singleton helper and functions
_default_store: BotAccessStore | None = None


def get_bot_store() -> BotAccessStore:
    global _default_store
    if _default_store is None:
        _default_store = BotAccessStore()
    return _default_store


def is_whitelisted(chat_id: int) -> bool:
    return get_bot_store().is_whitelisted(chat_id)


def add_whitelisted(chat_id: int, user_id: int, username: str = "", first_name: str = "", last_name: str = "", pin: str = "") -> bool:
    return get_bot_store().add_whitelisted(chat_id, user_id, username, first_name, last_name, pin)


def remove_whitelisted(user_id: int) -> bool:
    return get_bot_store().remove_whitelisted(user_id)


def get_whitelisted_users() -> list[dict[str, Any]]:
    return get_bot_store().get_whitelisted_users()


def record_pending_request(user_id: int, chat_id: int, username: str = "", first_name: str = "", last_name: str = "", language_code: str = "", admin_message_id: int = 0) -> int:
    return get_bot_store().record_pending_request(user_id, chat_id, username, first_name, last_name, language_code, admin_message_id)


def get_pending_by_user(user_id: int) -> dict[str, Any] | None:
    return get_bot_store().get_pending_by_user(user_id)


def get_pending_by_admin_message_id(msg_id: int) -> dict[str, Any] | None:
    return get_bot_store().get_pending_by_admin_message_id(msg_id)


def list_pending_requests() -> list[dict[str, Any]]:
    return get_bot_store().list_pending_requests()


def assign_pin_to_request(user_id: int, pin: str) -> bool:
    return get_bot_store().assign_pin_to_request(user_id, pin)


def validate_and_consume_pin(pin: str, user_id: int) -> bool:
    return get_bot_store().validate_and_consume_pin(pin, user_id)
