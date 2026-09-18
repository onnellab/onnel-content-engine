from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_unit_tests import UnexpectedNetworkAccess, main, offline_network


class OfflineRunnerTest(unittest.TestCase):
    def test_dns_and_connections_are_blocked_and_recorded(self):
        with offline_network() as attempts:
            with self.assertRaises(UnexpectedNetworkAccess):
                socket.getaddrinfo('example.test', 443)
            with self.assertRaises(UnexpectedNetworkAccess):
                socket.create_connection(('example.test', 443))
            with socket.socket() as sock:
                for call in (lambda: sock.connect(('127.0.0.1', 80)), lambda: sock.connect_ex(('127.0.0.1', 80))):
                    with self.assertRaises(UnexpectedNetworkAccess):
                        call()
            self.assertEqual(len(attempts), 4)

    def test_guard_restores_previous_adapters(self):
        before = socket.create_connection
        with offline_network():
            self.assertIsNot(socket.create_connection, before)
        self.assertIs(socket.create_connection, before)

    def test_caught_network_error_remains_recorded(self):
        with offline_network() as attempts:
            try:
                socket.getaddrinfo('example.test', 443)
            except Exception:
                pass
            self.assertEqual(len(attempts), 1)

    def test_empty_discovery_is_an_error_not_success(self):
        with patch.object(sys, 'argv', ['run_unit_tests.py', '--pattern', 'no-such-test-file.py']):
            self.assertEqual(main(), 2)


if __name__ == '__main__':
    unittest.main()
