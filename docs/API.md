# NPM Monitor REST API Documentation

## Overview
The NPM Monitor API (`npm-api`) provides a high-performance REST interface to access traffic logs, blocklists, and system statistics. It runs on port **8001** and is built with FastAPI.

### Base URL
`http://<your-host>:8001`

### Interactive Documentation
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

---

## Endpoints

### 1. System Statistics
`GET /stats`

Returns aggregated system metrics.

**Response**:
```json
{
  "total_rows": 1250430,
  "blocked_count": 42,
  "table_size": "1.2 GB"
}
```

### 2. Blocklist
`GET /blocklist`

Returns all currently active IP blocks, including AI analysis results if available.

**Response**:
```json
[
  {
    "ip_address": "1.2.3.4",
    "reason": "Honey-Path triggered: /.env",
    "blocked_at": "2026-03-14T12:00:00Z",
    "block_until": "2027-03-14T12:00:00Z",
    "threat_level": "Critical"
  }
]
```

### 3. Traffic Data
`GET /traffic/recent?limit=100`

Returns the most recent traffic log entries.

`GET /traffic/top-ips?limit=10`

Returns the most active IP addresses.

### 4. Management
`POST /blocking/unblock/{ip}`

Manually removes an IP from the blocklist.

---

## Integration Examples

### Python
```python
import requests

response = requests.get("http://npm-api:8001/stats")
data = response.json()
print(f"Total processed requests: {data['total_rows']}")
```

### Bash (cURL)
```bash
curl -X POST http://localhost:8001/blocking/unblock/1.2.3.4
```
