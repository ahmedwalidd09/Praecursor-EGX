from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from praecursor.notifications.bot_hub import TelegramBotHub
from praecursor.notifications.telegram import TelegramClient, TelegramSettings
from praecursor.storage.bot_store import BotAccessStore


class DummyTelegramClient(TelegramClient):
    """Mock TelegramClient for testing without real network calls."""

    def __init__(self, settings: TelegramSettings):
        super().__init__(settings)
        self.sent_messages: list[dict] = []
        self.sent_photos: list[dict] = []
        self.next_message_id = 100

    def send_message(
        self,
        text: str,
        chat_id: str | int | None = None,
        parse_mode: str = "HTML",
        reply_to_message_id: int | None = None,
        max_retries: int = 1,
    ) -> dict:
        self.next_message_id += 1
        target_cid = str(chat_id) if chat_id is not None else self.settings.chat_id
        entry = {
            "chat_id": target_cid,
            "text": text,
            "parse_mode": parse_mode,
            "reply_to_message_id": reply_to_message_id,
            "message_id": self.next_message_id,
        }
        self.sent_messages.append(entry)
        return {
            "ok": True,
            "result": {
                "message_id": self.next_message_id,
                "chat": {"id": int(target_cid) if target_cid.isdigit() else 1},
                "text": text,
            },
        }

    def send_photo(
        self,
        photo_path: Path,
        caption: str = "",
        parse_mode: str = "HTML",
        chat_id: str | int | None = None,
        reply_to_message_id: int | None = None,
    ) -> dict:
        self.next_message_id += 1
        target_cid = str(chat_id) if chat_id is not None else self.settings.chat_id
        entry = {
            "chat_id": target_cid,
            "photo_path": photo_path,
            "caption": caption,
            "message_id": self.next_message_id,
        }
        self.sent_photos.append(entry)
        return {
            "ok": True,
            "result": {
                "message_id": self.next_message_id,
                "chat": {"id": int(target_cid) if target_cid.isdigit() else 1},
            },
        }


class TestBotAccessStore(unittest.TestCase):
    """Test suite for BotAccessStore storage, tables, and JSON mirroring."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_praecursor.db"
        self.json_path = Path(self.temp_dir.name) / "test_whitelist.json"
        self.store = BotAccessStore(database_path=self.db_path, json_path=self.json_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_whitelist_storage_and_retrieval(self):
        # 1. Initially not whitelisted
        self.assertFalse(self.store.is_whitelisted(1001))

        # 2. Add to whitelist
        added = self.store.add_whitelisted(
            chat_id=1001,
            user_id=1001,
            username="investor_pro",
            first_name="Karim",
            last_name="Nabil",
            pin="VIP777",
        )
        self.assertTrue(added)
        self.assertTrue(self.store.is_whitelisted(1001))

        # 3. Retrieve records
        users = self.store.get_whitelisted_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["chat_id"], 1001)
        self.assertEqual(users[0]["username"], "investor_pro")
        self.assertEqual(users[0]["pin_used"], "VIP777")

        # 4. Verify JSON mirror updated
        self.assertTrue(self.json_path.exists())
        with open(self.json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        self.assertEqual(len(json_data), 1)
        self.assertEqual(json_data[0]["chat_id"], 1001)

        # 5. Revoke user
        revoked = self.store.remove_whitelisted(1001)
        self.assertTrue(revoked)
        self.assertFalse(self.store.is_whitelisted(1001))
        self.assertEqual(len(self.store.get_whitelisted_users()), 0)

    def test_pending_request_creation_and_pin_assignment(self):
        # 1. Record pending request
        req_id = self.store.record_pending_request(
            user_id=2002,
            chat_id=2002,
            username="trader_cairo",
            first_name="Tarek",
            last_name="Samir",
            language_code="ar",
            admin_message_id=505,
        )
        self.assertGreater(req_id, 0)

        # 2. Retrieve by user and admin msg id
        p1 = self.store.get_pending_by_user(2002)
        self.assertIsNotNone(p1)
        self.assertEqual(p1["username"], "trader_cairo")
        self.assertEqual(p1["status"], "PENDING")

        p2 = self.store.get_pending_by_admin_message_id(505)
        self.assertIsNotNone(p2)
        self.assertEqual(p2["user_id"], 2002)

        # 3. List pending
        p_list = self.store.list_pending_requests()
        self.assertEqual(len(p_list), 1)

        # 4. Assign PIN
        assigned = self.store.assign_pin_to_request(user_id=2002, pin="EGYPT99")
        self.assertTrue(assigned)
        p_updated = self.store.get_pending_by_user(2002)
        self.assertEqual(p_updated["assigned_pin"], "EGYPT99")

    def test_pin_consumption_and_whitelisting(self):
        # 1. Record request & assign PIN
        self.store.record_pending_request(user_id=3003, chat_id=3003, username="user3")
        self.store.assign_pin_to_request(user_id=3003, pin="ALPHA123")

        # 2. Validation with wrong PIN should fail
        self.assertFalse(self.store.validate_and_consume_pin("WRONG", user_id=3003))

        # 3. Validation with wrong user ID should fail
        self.assertFalse(self.store.validate_and_consume_pin("ALPHA123", user_id=9999))

        # 4. Valid PIN consumption
        consumed = self.store.validate_and_consume_pin("ALPHA123", user_id=3003)
        self.assertTrue(consumed)

        # 5. Cannot be reused
        self.assertFalse(self.store.validate_and_consume_pin("ALPHA123", user_id=3003))

        # 6. Pending request status marked APPROVED
        pending_after = self.store.get_pending_by_user(3003)
        self.assertIsNone(pending_after)  # get_pending_by_user only returns status='PENDING'


class TestTelegramBotHubFlow(unittest.TestCase):
    """Test suite for TelegramBotHub interactive permission-slip and reply-to-approve flow."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_hub.db"
        self.json_path = Path(self.temp_dir.name) / "test_hub.json"
        self.store = BotAccessStore(database_path=self.db_path, json_path=self.json_path)

        self.settings = TelegramSettings(bot_token="TEST_BOT_TOKEN", chat_id="99999")
        self.client = DummyTelegramClient(self.settings)
        self.hub = TelegramBotHub(settings=self.settings, client=self.client, store=self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_superadmin_registered(self):
        # Admin should automatically be whitelisted
        self.assertTrue(self.store.is_whitelisted(99999))
        self.assertTrue(self.hub.is_admin(99999))
        self.assertTrue(self.hub.is_admin("99999"))

    def test_unwhitelisted_user_permission_slip_flow(self):
        # New user sends /start
        msg = {
            "message_id": 10,
            "chat": {"id": 1234},
            "from": {
                "id": 1234,
                "username": "candidate_trader",
                "first_name": "Mostafa",
                "last_name": "Gamal",
                "language_code": "en",
            },
            "text": "/start",
        }

        res = self.hub.handle_message(msg)
        self.assertEqual(res["action"], "access_requested")

        # User receives permission-slip message
        user_msgs = [m for m in self.client.sent_messages if m["chat_id"] == "1234"]
        self.assertEqual(len(user_msgs), 1)
        self.assertIn("Access Restricted", user_msgs[0]["text"])

        # Admin receives alert message
        admin_msgs = [m for m in self.client.sent_messages if m["chat_id"] == "99999"]
        self.assertGreaterEqual(len(admin_msgs), 1)
        alert_msg = admin_msgs[-1]
        self.assertIn("NEW ACCESS REQUEST", alert_msg["text"])
        self.assertIn("candidate_trader", alert_msg["text"])
        admin_alert_id = alert_msg["message_id"]

        # Request is stored as pending
        pending = self.store.get_pending_by_user(1234)
        self.assertIsNotNone(pending)
        self.assertEqual(pending["admin_message_id"], admin_alert_id)

    def test_reply_to_approve_flow(self):
        # 1. Setup pending request with known admin_message_id
        admin_alert_msg_id = 777
        self.store.record_pending_request(
            user_id=5555,
            chat_id=5555,
            username="investor_ali",
            first_name="Ali",
            last_name="Hassan",
            language_code="en",
            admin_message_id=admin_alert_msg_id,
        )

        # 2. SuperAdmin replies to that alert with PIN "VIP88"
        admin_reply_msg = {
            "message_id": 800,
            "chat": {"id": 99999},
            "from": {"id": 99999, "username": "SuperAdmin"},
            "text": "VIP88",
            "reply_to_message": {"message_id": admin_alert_msg_id},
        }

        res = self.hub.handle_message(admin_reply_msg)
        self.assertEqual(res["action"], "admin_reply_approved")
        self.assertEqual(res["pin"], "VIP88")

        # 3. User received approval notification with /pin VIP88
        user_msgs = [m for m in self.client.sent_messages if m["chat_id"] == "5555"]
        self.assertTrue(any("VIP88" in m["text"] for m in user_msgs))

        # 4. User sends "/pin VIP88"
        user_pin_msg = {
            "message_id": 805,
            "chat": {"id": 5555},
            "from": {"id": 5555, "username": "investor_ali"},
            "text": "/pin VIP88",
        }
        res_pin = self.hub.handle_message(user_pin_msg)
        self.assertEqual(res_pin["action"], "pin_verified")

        # 5. User is now permanently whitelisted
        self.assertTrue(self.store.is_whitelisted(5555))

        # 6. Admin was notified of verification
        admin_msgs = [m for m in self.client.sent_messages if m["chat_id"] == "99999"]
        self.assertTrue(any("User Verified" in m["text"] for m in admin_msgs))

    def test_admin_commands(self):
        # Create pending user
        self.store.record_pending_request(user_id=7777, chat_id=7777, username="pending_user")

        # /pending
        res = self.hub.handle_message({
            "message_id": 901,
            "chat": {"id": 99999},
            "from": {"id": 99999},
            "text": "/pending",
        })
        self.assertEqual(res["action"], "admin_pending_listed")

        # /code 7777 SECURE44
        res = self.hub.handle_message({
            "message_id": 902,
            "chat": {"id": 99999},
            "from": {"id": 99999},
            "text": "/code 7777 SECURE44",
        })
        self.assertEqual(res["action"], "admin_code_assigned")

        # User activates with direct code entry "SECURE44"
        res = self.hub.handle_message({
            "message_id": 903,
            "chat": {"id": 7777},
            "from": {"id": 7777, "username": "pending_user"},
            "text": "SECURE44",
        })
        self.assertEqual(res["action"], "pin_verified")
        self.assertTrue(self.store.is_whitelisted(7777))

        # /whitelist
        res = self.hub.handle_message({
            "message_id": 904,
            "chat": {"id": 99999},
            "from": {"id": 99999},
            "text": "/whitelist",
        })
        self.assertEqual(res["action"], "admin_whitelist_listed")

        # /revoke 7777
        res = self.hub.handle_message({
            "message_id": 905,
            "chat": {"id": 99999},
            "from": {"id": 99999},
            "text": "/revoke 7777",
        })
        self.assertEqual(res["action"], "admin_revoked")
        self.assertFalse(self.store.is_whitelisted(7777))

        # /broadcast announcement
        res = self.hub.handle_message({
            "message_id": 906,
            "chat": {"id": 99999},
            "from": {"id": 99999},
            "text": "/broadcast Market open at 10:00 AM Cairo time.",
        })
        self.assertEqual(res["action"], "admin_broadcast")

    def test_whitelisted_user_commands(self):
        # Authorize a user
        self.store.add_whitelisted(chat_id=6006, user_id=6006, username="active_trader")

        # /help
        res = self.hub.handle_message({
            "message_id": 1001,
            "chat": {"id": 6006},
            "from": {"id": 6006},
            "text": "/help",
        })
        self.assertEqual(res["action"], "whitelisted_help")

        # /status
        res = self.hub.handle_message({
            "message_id": 1002,
            "chat": {"id": 6006},
            "from": {"id": 6006},
            "text": "/status",
        })
        self.assertEqual(res["action"], "whitelisted_status")

        # /regime
        res = self.hub.handle_message({
            "message_id": 1003,
            "chat": {"id": 6006},
            "from": {"id": 6006},
            "text": "/regime",
        })
        self.assertEqual(res["action"], "whitelisted_regime")

    def test_outbound_broadcast(self):
        # Authorize 2 users
        self.store.add_whitelisted(chat_id=8001, user_id=8001, username="u1")
        self.store.add_whitelisted(chat_id=8002, user_id=8002, username="u2")

        # Broadcast text message
        sent_count = self.hub.broadcast_message("📢 Global Scan Announcement")
        # Recipients: 8001, 8002, and SuperAdmin 99999
        self.assertEqual(sent_count, 3)

        # Broadcast scan briefing with mock result
        mock_result = MagicMock()
        mock_result.generated_at = datetime.now(timezone.utc)
        mock_result.next_day_results = []
        with patch.object(self.hub.formatter, "format_scanner_result", return_value="<b>Scan Briefing</b>"):
            res = self.hub.broadcast_scan_briefing(run_result=mock_result, send_charts=False, verbose=False)
            self.assertTrue(res["ok"])
            self.assertEqual(res["sent_count"], 3)


if __name__ == "__main__":
    unittest.main()
