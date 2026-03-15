import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.blocking import IPBlocker
from src.config import app_config
import redis

class TestBlockingIntegration(unittest.TestCase):
    def setUp(self):
        # Mocking external components to avoid side effects
        self.patcher_db = patch('src.blocking.update_request_counters')
        self.patcher_block = patch('src.blocking.IPBlocker._block_ip')
        self.patcher_notify = patch('src.blocking.send_notification')
        self.patcher_whitelist = patch('src.blocking.IPBlocker._is_whitelisted', return_value=False)
        self.patcher_asn = patch('src.blocking.IPBlocker._is_asn_blocked', return_value=False)
        
        self.mock_update_counters = self.patcher_db.start()
        self.mock_block_ip = self.patcher_block.start()
        self.mock_notify = self.patcher_notify.start()
        self.mock_is_whitelisted = self.patcher_whitelist.start()
        self.mock_is_asn_blocked = self.patcher_asn.start()
        
        self.blocker = IPBlocker(use_firewall=False)
        self.test_ip = "1.2.3.4"

    def tearDown(self):
        self.patcher_db.stop()
        self.patcher_block.stop()
        self.patcher_notify.stop()
        self.patcher_whitelist.stop()
        self.patcher_asn.stop()

    def test_honey_path_blocking(self):
        """Test if accessing a honey path triggers an instant block."""
        print("\nTesting Honey-Path Blocking...")
        honey_path = "/.env"
        reason = self.blocker.check_request(self.test_ip, 200, honey_path)
        
        self.assertIsNotNone(reason)
        self.assertIn("Honey-Path", reason)
        self.mock_block_ip.assert_called_once()
        print(f"SUCCESS: Honey-path '{honey_path}' triggered block: {reason}")

    def test_sqli_waf_blocking(self):
        """Test if SQL injection pattern triggers an instant block."""
        print("\nTesting SQLi WAF Blocking...")
        sqli_path = "/products?id=1' UNION SELECT NULL--"
        reason = self.blocker.check_request(self.test_ip, 200, sqli_path)
        
        self.assertIsNotNone(reason)
        self.assertIn("SQL-Injection", reason)
        self.mock_block_ip.assert_called_once()
        print(f"SUCCESS: SQLi pattern triggered block: {reason}")

    def test_malicious_ua_blocking(self):
        """Test if a malicious User-Agent triggers an instant block."""
        print("\nTesting Malicious User-Agent Blocking...")
        malicious_ua = "Mozilla/5.0 (compatible; nmap/7.80; +https://nmap.org/book/nse.html)"
        reason = self.blocker.check_request(self.test_ip, 200, "/", user_agent=malicious_ua)
        
        self.assertIsNotNone(reason)
        self.assertIn("Bösartiger User-Agent", reason)
        self.mock_block_ip.assert_called_once()
        print(f"SUCCESS: User-Agent '{malicious_ua}' triggered block: {reason}")

    def test_404_threshold_blocking(self):
        """Test if exceeding 404 threshold triggers a block."""
        print("\nTesting 404 Threshold Blocking...")
        # Simulate reaching threshold
        self.mock_update_counters.return_value = {
            "count_404": app_config.max_404_errors,
            "count_403": 0,
            "count_5xx": 0,
            "count_suspicious": 0,
            "total_failed": app_config.max_404_errors,
            "total_requests": app_config.max_404_errors
        }
        
        reason = self.blocker.check_request(self.test_ip, 404, "/not-found")
        
        self.assertIsNotNone(reason)
        self.assertIn("Too many 404 errors", reason)
        self.mock_block_ip.assert_called_once()
        print(f"SUCCESS: 404 threshold triggered block: {reason}")

    def test_rate_limit_blocking(self):
        """Test if rate limit triggers a block."""
        print("\nTesting Rate-Limit Blocking...")
        # Simulate reaching rate limit (requests per 5 minutes)
        self.mock_update_counters.return_value = {
            "count_404": 0,
            "count_403": 0,
            "count_5xx": 0,
            "count_suspicious": 0,
            "total_failed": 0,
            "total_requests": (app_config.max_requests_per_minute * 5) + 1
        }
        
        reason = self.blocker.check_request(self.test_ip, 200, "/")
        
        self.assertIsNotNone(reason)
        self.assertIn("Rate limit exceeded", reason)
        self.mock_block_ip.assert_called_once()
        print(f"SUCCESS: Rate limit triggered block: {reason}")

if __name__ == '__main__':
    unittest.main()
