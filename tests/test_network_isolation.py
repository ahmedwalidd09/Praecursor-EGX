"""
Unit test to verify network isolation / socket blocking fixture in Praecursor-EGX pytest configuration.
"""

import socket
import pytest


def test_network_isolation_guard_blocks_outbound_sockets():
    """Verify that attempting an external socket connection raises RuntimeError."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            sock.connect(("8.8.8.8", 80))
        assert "Network access disabled during automated test runs" in str(exc_info.value)
    finally:
        sock.close()
