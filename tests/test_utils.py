from src.utils import calculate_error_rate, format_bytes, format_number, get_status_category


def test_format_number():
    assert format_number(100) == "100"
    assert format_number(1500) == "1,500"
    assert format_number(1500000) == "1,500,000"

def test_format_bytes():
    assert format_bytes(500) == "500.0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1024 * 1024) == "1.0 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"

def test_calculate_error_rate():
    assert calculate_error_rate(100, 5) == 5.0
    assert calculate_error_rate(0, 0) == 0.0
    assert calculate_error_rate(100, 0) == 0.0

def test_get_status_category():
    assert get_status_category(200) == "2xx Success"
    assert get_status_category(301) == "3xx Redirect"
    assert get_status_category(404) == "4xx Client Error"
    assert get_status_category(502) == "5xx Server Error"
    assert get_status_category(100) == "1xx Informational"
