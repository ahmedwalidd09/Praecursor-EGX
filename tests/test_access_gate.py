"""Unit tests for Telegram Access Gate and HMAC Machine Whitelisting."""

from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from praecursor.security import access_gate


class TestAccessGate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.orig_whitelist_file = access_gate.WHITELIST_FILE
        access_gate.WHITELIST_FILE = self.temp_path / "whitelist.lic"

    def tearDown(self):
        access_gate.WHITELIST_FILE = self.orig_whitelist_file
        self.temp_dir.cleanup()

    def test_fingerprint_and_node_id_format(self):
        fp = access_gate.get_machine_fingerprint()
        self.assertIsInstance(fp, str)
        self.assertTrue(len(fp) > 0)

        node_id = access_gate.get_short_node_id()
        self.assertTrue(node_id.startswith("NODE-"))
        self.assertEqual(len(node_id), 11)  # "NODE-" + 6 hex characters

    def test_machine_not_whitelisted_initially(self):
        self.assertFalse(access_gate.is_machine_whitelisted())

    def test_whitelist_current_machine_creates_valid_license(self):
        pin = "9482"
        success = access_gate.whitelist_current_machine(approved_pin=pin)
        self.assertTrue(success)
        self.assertTrue(access_gate.WHITELIST_FILE.exists())

        # Verify license can be validated
        self.assertTrue(access_gate.is_machine_whitelisted())

        # Verify license content
        data = json.loads(access_gate.WHITELIST_FILE.read_text(encoding="utf-8"))
        self.assertEqual(data["pin"], pin)
        self.assertEqual(data["node_id"], access_gate.get_short_node_id())
        self.assertIn("signature", data)
        self.assertIn("whitelisted_at", data)

    def test_tampered_license_is_rejected(self):
        access_gate.whitelist_current_machine(approved_pin="1234")
        self.assertTrue(access_gate.is_machine_whitelisted())

        # Tamper with the signature
        data = json.loads(access_gate.WHITELIST_FILE.read_text(encoding="utf-8"))
        data["signature"] = "tampered_signature_hex_0000000000000000"
        access_gate.WHITELIST_FILE.write_text(json.dumps(data), encoding="utf-8")

        self.assertFalse(access_gate.is_machine_whitelisted())

    def test_send_telegram_access_request_formatting(self):
        captured_requests = []

        class DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def read(self):
                return json.dumps({"ok": True, "result": {"message_id": 999}}).encode("utf-8")

        def mock_urlopen(req, timeout=10):
            captured_requests.append(req)
            return DummyResponse()

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            ok, msg = access_gate.send_telegram_access_request(bot_token="test_token_123", chat_id="8196296723")
            self.assertTrue(ok)
            self.assertIn("dispatched", msg.lower())

        self.assertEqual(len(captured_requests), 1)
        req = captured_requests[0]
        self.assertEqual(req.get_full_url(), "https://api.telegram.org/bottest_token_123/sendMessage")
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["chat_id"], "8196296723")
        self.assertEqual(payload["parse_mode"], "HTML")
        node_id = access_gate.get_short_node_id()
        self.assertIn(f"<b>Node ID:</b> <code>{node_id}</code>", payload["text"])
        self.assertIn(f"/approve {node_id}", payload["text"])

    def test_check_telegram_approval_success_with_pin(self):
        node_id = access_gate.get_short_node_id()
        chat_id = "8196296723"

        mock_updates_payload = {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "chat": {"id": int(chat_id)},
                        "text": f"/approve {node_id} 7788",
                    },
                }
            ],
        }

        class DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def read(self):
                return json.dumps(mock_updates_payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=DummyResponse()):
            ok, msg = access_gate.check_telegram_approval(
                entered_pin="7788",
                bot_token="test_token",
                chat_id=chat_id,
            )
            self.assertTrue(ok)
            self.assertIn("PIN verified", msg)
            self.assertTrue(access_gate.is_machine_whitelisted())

    def test_check_telegram_approval_mismatched_pin(self):
        node_id = access_gate.get_short_node_id()
        chat_id = "8196296723"

        mock_updates_payload = {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "chat": {"id": int(chat_id)},
                        "text": f"/approve {node_id} 7788",
                    },
                }
            ],
        }

        class DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def read(self):
                return json.dumps(mock_updates_payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=DummyResponse()):
            ok, msg = access_gate.check_telegram_approval(
                entered_pin="9999",
                bot_token="test_token",
                chat_id=chat_id,
            )
            self.assertFalse(ok)
            self.assertIn("does not match", msg)
            self.assertFalse(access_gate.is_machine_whitelisted())

    def test_check_telegram_approval_auto_approves_without_entered_pin(self):
        node_id = access_gate.get_short_node_id()
        chat_id = "8196296723"

        mock_updates_payload = {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "chat": {"id": int(chat_id)},
                        "text": f"/grant {node_id} 4321",
                    },
                }
            ],
        }

        class DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def read(self):
                return json.dumps(mock_updates_payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=DummyResponse()):
            ok, msg = access_gate.check_telegram_approval(
                entered_pin="",
                bot_token="test_token",
                chat_id=chat_id,
            )
            self.assertTrue(ok)
            self.assertIn("Admin approved code 4321", msg)
            self.assertTrue(access_gate.is_machine_whitelisted())

    def test_check_telegram_approval_ignores_unauthorized_chat(self):
        node_id = access_gate.get_short_node_id()
        chat_id = "8196296723"

        mock_updates_payload = {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "chat": {"id": 9999999},  # Unauthorized chat
                        "text": f"/approve {node_id} 7788",
                    },
                }
            ],
        }

        class DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

            def read(self):
                return json.dumps(mock_updates_payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=DummyResponse()):
            ok, msg = access_gate.check_telegram_approval(
                entered_pin="7788",
                bot_token="test_token",
                chat_id=chat_id,
            )
            self.assertFalse(ok)
            self.assertIn("No approval found", msg)
            self.assertFalse(access_gate.is_machine_whitelisted())


class TestDashboardAccessGate(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from praecursor.cli.dashboard import app

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.orig_whitelist_file = access_gate.WHITELIST_FILE
        access_gate.WHITELIST_FILE = self.temp_path / "whitelist.lic"
        self.client = TestClient(app)

    def tearDown(self):
        access_gate.WHITELIST_FILE = self.orig_whitelist_file
        self.temp_dir.cleanup()

    def test_gate_renders_when_unauthorized(self):
        # Machine is not whitelisted
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("INSTITUTIONAL ACCESS GATE", resp.text)
        self.assertIn(access_gate.get_short_node_id(), resp.text)

        resp_dash = self.client.get("/dashboard")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn("INSTITUTIONAL ACCESS GATE", resp_dash.text)

    def test_mission_control_renders_when_whitelisted(self):
        # Whitelist the machine
        access_gate.whitelist_current_machine("1234")
        self.assertTrue(access_gate.is_machine_whitelisted())

        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Mission Control", resp.text)
        self.assertNotIn("INSTITUTIONAL ACCESS GATE", resp.text)

    def test_api_access_status(self):
        resp = self.client.get("/api/access/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["whitelisted"])
        self.assertEqual(data["node_id"], access_gate.get_short_node_id())

        access_gate.whitelist_current_machine("5678")
        resp2 = self.client.get("/api/access/status")
        self.assertTrue(resp2.json()["whitelisted"])

    @patch("praecursor.cli.dashboard.send_telegram_access_request")
    def test_api_access_request(self, mock_send):
        mock_send.return_value = (True, "Access request dispatched to Telegram.")
        resp = self.client.post("/api/access/request")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        mock_send.assert_called_once()

    @patch("praecursor.cli.dashboard.check_telegram_approval")
    def test_api_access_verify(self, mock_check):
        mock_check.return_value = (True, "PIN verified! Terminal whitelisted permanently.")
        resp = self.client.post("/api/access/verify", json={"pin": "8492"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        mock_check.assert_called_once_with(entered_pin="8492")


if __name__ == "__main__":
    unittest.main()
