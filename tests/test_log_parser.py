import pytest
from datetime import datetime
from src.log_parser import parse_log_line, should_ignore_ip


def test_should_ignore_ip():
    assert should_ignore_ip("127.0.0.1") is True
    assert should_ignore_ip("192.168.1.1") is True
    assert should_ignore_ip("10.0.0.1") is True
    assert should_ignore_ip("8.8.8.8") is False


def test_parse_log_line():
    line = '[12/Oct/2023:14:32:10 +0000] - 200 200 - GET https example.com "/api/data" [Client 8.8.8.8] [Length 1024] [Gzip -] [Sent-to -] "Mozilla/5.0" "https://google.com"'
    parsed = parse_log_line(line)
    assert parsed is not None
    assert parsed["status"] == 200
    assert parsed["method"] == "GET"
    assert parsed["scheme"] == "https"
    assert parsed["host"] == "example.com"
    assert parsed["path"] == "/api/data"
    assert parsed["remote_addr"] == "8.8.8.8"
    assert parsed["response_length"] == 1024
    assert parsed["user_agent"] == "Mozilla/5.0"
    assert parsed["referer"] == "https://google.com"


def test_parse_log_line_ignored_ip():
    line = '[12/Oct/2023:14:32:10 +0000] - 200 200 - GET https example.com "/api/data" [Client 192.168.1.1] [Length 1024] [Gzip -] [Sent-to -] "Mozilla/5.0" "https://google.com"'
    parsed = parse_log_line(line)
    assert parsed is None


def test_parse_log_line_ipv6():
    """Test parsing with IPv6 addresses."""
    line = '[12/Oct/2023:14:32:10 +0000] - 200 200 - GET https example.com "/api/data" [Client 2001:db8::1] [Length 1024] [Gzip -] [Sent-to -] "Mozilla/5.0" "https://google.com"'
    parsed = parse_log_line(line)
    assert parsed is not None
    assert parsed["remote_addr"] == "2001:db8::1"


def test_parse_log_line_with_cloudflare_ip():
    """Test that Cloudflare IPs are ignored (filtered out)."""
    line = '[12/Oct/2023:14:32:10 +0000] - 200 200 - GET https example.com "/api/data" [Client 173.245.48.1] [Length 1024] [Gzip -] [Sent-to -] "Mozilla/5.0" "-"'
    parsed = parse_log_line(line)
    # Cloudflare IPs are filtered by should_ignore_ip
    assert parsed is None


def test_should_ignore_ipv6():
    """Test IPv6 private address filtering."""
    assert should_ignore_ip("::1") is True  # Localhost IPv6
    assert should_ignore_ip("fe80::1") is True  # Link-local
    assert should_ignore_ip("fc00::1") is True  # Unique local
    assert should_ignore_ip("2001:db8::1") is False  # Public IPv6


def test_parse_log_line_with_dash_referer():
    """Test that dash referer is converted to None."""
    line = '[12/Oct/2023:14:32:10 +0000] - 200 200 - GET https example.com "/api/data" [Client 8.8.8.8] [Length 1024] [Gzip -] [Sent-to -] "Mozilla/5.0" "-"'
    parsed = parse_log_line(line)
    assert parsed is not None
    assert parsed["referer"] is None


def test_parse_log_line_with_dash_length():
    """Test that dash length is converted to 0."""
    line = '[12/Oct/2023:14:32:10 +0000] - 200 200 - GET https example.com "/api/data" [Client 8.8.8.8] [Length -] [Gzip -] [Sent-to -] "Mozilla/5.0" "-"'
    parsed = parse_log_line(line)
    assert parsed is not None
    assert parsed["response_length"] == 0
