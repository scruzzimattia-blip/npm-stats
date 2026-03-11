"""Tests for IP blocking module."""

import pytest
from datetime import datetime, timedelta
from src.blocking import IPBlocker


def test_ip_blocker_initialization():
    """Test IP blocker initialization."""
    blocker = IPBlocker()
    
    assert blocker.request_counts == {}
    assert blocker.blocked_ips == {}
    assert blocker.whitelisted_ips == set()


def test_track_404_errors():
    """Test tracking of 404 errors."""
    blocker = IPBlocker()
    ip = "192.168.1.100"
    
    # Track multiple 404 errors
    for _ in range(10):
        result = blocker.check_request(ip, 404, "/nonexistent", "example.com")
        assert result is None  # Should not block yet
    
    # Check counters
    assert blocker.request_counts[ip]["404"] == 10


def test_block_ip_on_threshold():
    """Test IP blocking when threshold is exceeded."""
    blocker = IPBlocker()
    blocker.max_404_errors = 5  # Lower threshold for testing
    ip = "192.168.1.100"
    
    # Trigger blocking
    for _ in range(5):
        result = blocker.check_request(ip, 404, "/nonexistent", "example.com")
    
    # Should block on 5th request
    assert result is not None
    assert "404" in result
    assert blocker.is_blocked(ip)


def test_whitelisted_ip_never_blocked():
    """Test that whitelisted IPs are never blocked."""
    blocker = IPBlocker()
    ip = "192.168.1.100"
    
    # Whitelist IP
    blocker.whitelist_ip(ip)
    
    # Try to trigger blocking
    for _ in range(100):
        result = blocker.check_request(ip, 404, "/nonexistent", "example.com")
        assert result is None
    
    # Should not be blocked
    assert not blocker.is_blocked(ip)


def test_suspicious_path_detection():
    """Test detection of suspicious paths."""
    blocker = IPBlocker()
    ip = "192.168.1.100"
    
    # Access suspicious path multiple times
    for _ in range(5):
        result = blocker.check_request(ip, 200, "/wp-admin", "example.com")
    
    # Should block due to suspicious activity
    assert result is not None
    assert "Suspicious" in result or "suspicious" in result.lower()


def test_block_expiration():
    """Test that blocks expire correctly."""
    blocker = IPBlocker()
    blocker.block_duration = 1  # 1 second for testing
    ip = "192.168.1.100"
    
    # Block IP
    blocker._block_ip(ip, "Test block")
    assert blocker.is_blocked(ip)
    
    # Wait for block to expire
    import time
    time.sleep(2)
    
    # Should no longer be blocked
    assert not blocker.is_blocked(ip)


def test_unblock_ip():
    """Test manual unblocking of IPs."""
    blocker = IPBlocker()
    ip = "192.168.1.100"
    
    # Block IP
    blocker._block_ip(ip, "Test block")
    assert blocker.is_blocked(ip)
    
    # Unblock
    result = blocker.unblock_ip(ip)
    assert result is True
    assert not blocker.is_blocked(ip)


def test_get_blocked_ips():
    """Test retrieving list of blocked IPs."""
    blocker = IPBlocker()
    
    # Block multiple IPs
    blocker._block_ip("192.168.1.100", "Test 1")
    blocker._block_ip("192.168.1.101", "Test 2")
    
    blocked = blocker.get_blocked_ips()
    
    assert "192.168.1.100" in blocked
    assert "192.168.1.101" in blocked
    assert len(blocked) == 2


def test_get_stats():
    """Test blocking statistics."""
    blocker = IPBlocker()
    
    # Add some data
    blocker._block_ip("192.168.1.100", "Test")
    blocker.whitelist_ip("192.168.1.200")
    blocker.request_counts["192.168.1.150"] = {"404": 5}
    
    stats = blocker.get_stats()
    
    assert stats["total_blocked"] == 1
    assert stats["whitelisted"] == 1
    assert stats["tracked_ips"] == 1


def test_cleanup_old_timestamps():
    """Test cleanup of old timestamps."""
    blocker = IPBlocker()
    ip = "192.168.1.100"
    
    # Add old timestamp
    old_time = datetime.now() - timedelta(minutes=10)
    blocker.request_timestamps[ip].append(old_time)
    blocker.request_counts[ip]["404"] = 100
    
    # Cleanup
    blocker._cleanup_old_timestamps(ip, datetime.now())
    
    # Should reset counters when no recent requests
    assert len(blocker.request_timestamps[ip]) == 0
    assert blocker.request_counts[ip]["404"] == 0


def test_multiple_error_types():
    """Test tracking multiple error types."""
    blocker = IPBlocker()
    ip = "192.168.1.100"
    
    # Mix of errors
    blocker.check_request(ip, 404, "/path1", "example.com")
    blocker.check_request(ip, 403, "/path2", "example.com")
    blocker.check_request(ip, 500, "/path3", "example.com")
    
    # Check all counters
    assert blocker.request_counts[ip]["404"] == 1
    assert blocker.request_counts[ip]["403"] == 1
    assert blocker.request_counts[ip]["5xx"] == 1
    assert blocker.request_counts[ip]["total_failed"] == 3


def test_global_blocker_instance():
    """Test global blocker instance."""
    from src.blocking import get_blocker
    
    blocker1 = get_blocker()
    blocker2 = get_blocker()
    
    # Should be same instance
    assert blocker1 is blocker2