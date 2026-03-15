"""Tests for the firewall (iptables) module."""

import unittest
from unittest.mock import MagicMock, patch
import subprocess

from src.firewall import IptablesManager


class TestIptablesManager(unittest.TestCase):
    def setUp(self):
        # We need to patch the checks during initialization
        with patch.object(IptablesManager, "_check_iptables_available", return_value=True), \
             patch.object(IptablesManager, "_check_permissions", return_value=True):
            self.manager = IptablesManager()

    @patch("subprocess.run")
    def test_block_ip(self, mock_run):
        """Test blocking an IP address."""
        # Mock is_blocked to return False (not already blocked)
        with patch.object(self.manager, "is_blocked", return_value=False):
            mock_run.return_value = MagicMock(returncode=0)
            
            result = self.manager.block_ip("1.2.3.4", "Test reason")
            
            self.assertTrue(result)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            self.assertIn("iptables", args)
            self.assertIn("-A", args)
            self.assertIn("1.2.3.4", args)
            self.assertIn("DROP", args)

    @patch("subprocess.run")
    def test_unblock_ip(self, mock_run):
        """Test unblocking an IP address."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.unblock_ip("1.2.3.4")
        
        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-D", args)
        self.assertIn("1.2.3.4", args)

    @patch("subprocess.run")
    def test_is_blocked(self, mock_run):
        """Test checking if an IP is blocked."""
        # Mock successful check (returncode 0 means rule exists)
        mock_run.return_value = MagicMock(returncode=0)
        
        self.assertTrue(self.manager.is_blocked("1.2.3.4"))
        
        # Mock failed check (returncode != 0 means rule doesn't exist)
        mock_run.return_value = MagicMock(returncode=1)
        self.assertFalse(self.manager.is_blocked("1.1.1.1"))

    @patch("subprocess.run")
    def test_create_chain(self, mock_run):
        """Test creating the custom iptables chain."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.create_chain()
        
        self.assertTrue(result)
        # Should call iptables -N and iptables -C/-I
        self.assertGreaterEqual(mock_run.call_count, 2)

    @patch("subprocess.run")
    def test_flush_chain(self, mock_run):
        """Test flushing the chain."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = self.manager.flush_chain()
        
        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-F", args)


if __name__ == "__main__":
    unittest.main()
