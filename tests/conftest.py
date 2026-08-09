"""
Global pytest configuration and network isolation guard for Praecursor-EGX.
Guarantees zero external network access and zero credit usage during automated test runs.
"""

import sys
from pathlib import Path
import socket
import pytest

# Ensure tests/ and src/ are in sys.path for helper imports and module resolution
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def block_network_access(monkeypatch):
    """
    Autouse fixture that prevents tests from making live external network calls.
    Attempts to establish external socket connections will raise a RuntimeError.
    Allows loopback / localhost connections if inter-process or local service communication is needed.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        if isinstance(address, tuple) and len(address) > 0:
            host = address[0]
        else:
            host = str(address)

        # Allow loopback / localhost connections if needed for local test servers
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, address)

        raise RuntimeError(
            f"Network access disabled during automated test runs: attempted connection to {address}. "
            "All tests must use synthetic/mocked data to prevent API credit burn and external network dependencies."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
