"""Tests for authentication module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ipaddress import ip_address, ip_network


def test_ttl_cache_basic():
    """Test basic TTL cache functionality."""
    from src.log_parser import TTLCache
    import time
    
    cache = TTLCache(maxsize=2, ttl=10)
    
    call_count = 0
    
    @cache
    def expensive_function(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    result1 = expensive_function(5)
    assert result1 == 10
    assert call_count == 1
    
    result2 = expensive_function(5)
    assert result2 == 10
    assert call_count == 1  # Should use cache
    
    result3 = expensive_function(6)
    assert result3 == 12
    assert call_count == 2


def test_ttl_cache_lru_eviction():
    """Test LRU eviction in TTL cache."""
    from src.log_parser import TTLCache
    
    cache = TTLCache(maxsize=2, ttl=10)
    
    @cache
    def func(x):
        return x
    
    func(1)
    func(2)
    func(3)  # Should evict func(1) due to LRU
    
    # Verify cache size
    with cache._lock:
        assert len(cache._cache) <= 2


def test_ttl_cache_thread_safety():
    """Test that cache operations are thread-safe."""
    from src.log_parser import TTLCache
    import threading
    
    cache = TTLCache(maxsize=100, ttl=10)
    errors = []
    
    @cache
    def func(x):
        return x * 2
    
    def worker():
        try:
            for i in range(10):
                func(i)
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert len(errors) == 0


def test_ttl_cache_clear():
    """Test cache clearing functionality."""
    from src.log_parser import TTLCache
    
    cache = TTLCache(maxsize=10, ttl=10)
    
    @cache
    def func(x):
        return x
    
    func(1)
    func(2)
    func(3)
    
    cache.clear()
    
    with cache._lock:
        assert len(cache._cache) == 0