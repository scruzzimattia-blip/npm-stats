# API Documentation

## Overview

NPM Monitor provides a web-based dashboard for analyzing Nginx Proxy Manager traffic logs. This document describes the internal API and data flow.

## Architecture Components

### 1. Core Modules

#### `app.py` - Main Application
- **Purpose**: Streamlit dashboard entry point and UI rendering
- **Key Functions**:
  - `main()`: Application entry point with authentication check
  - `sync_logs()`: Trigger log synchronization and invalidate caches
  - `load_traffic_data()`: Load and cache traffic data from database

#### `auth.py` - Authentication Module
- **Purpose**: Handle user authentication and IP-based access control
- **Key Functions**:
  - `check_auth()`: Validate user credentials and IP access
  - `check_ip_access()`: Check if client IP is in allowed networks

#### `database.py` - Database Operations
- **Purpose**: PostgreSQL database connection and operations
- **Key Functions**:
  - `init_database()`: Initialize schema and indexes
  - `insert_traffic_batch()`: Batch insert log records
  - `load_traffic_df()`: Load traffic data as pandas DataFrame
  - `get_distinct_hosts()`: Get unique hostnames
  - `cleanup_old_data()`: Delete records older than retention period
  - `health_check()`: Verify database connectivity

#### `log_parser.py` - Log Parsing
- **Purpose**: Parse NPM access logs and extract structured data
- **Key Components**:
  - `TTLCache`: Thread-safe LRU cache with TTL support
  - `parse_log_line()`: Parse single log line into structured dict
  - `should_ignore_ip()`: Filter private and Cloudflare IPs
  - `get_geoip_info()`: Resolve GeoIP data for IP addresses

#### `sync.py` - Log Synchronization
- **Purpose**: Synchronize log files with database
- **Key Functions**:
  - `sync_logs()`: Main sync function that processes all log files
  - Uses ThreadPoolExecutor for parallel processing

### 2. Data Flow

```
NPM Logs → log_parser.py → sync.py → database.py → PostgreSQL
                                                      ↓
                                            app.py → Streamlit Dashboard
```

### 3. Database Schema

#### Traffic Table
```sql
CREATE TABLE traffic (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    host TEXT NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status INTEGER NOT NULL,
    remote_addr TEXT NOT NULL,
    user_agent TEXT,
    referer TEXT,
    response_length BIGINT,
    country_code CHAR(2),
    city TEXT,
    scheme TEXT,
    UNIQUE (time, host, remote_addr, path)
);
```

#### Indexes
- `idx_traffic_time`: Time-based queries (DESC)
- `idx_traffic_host`: Host filtering
- `idx_traffic_time_host`: Composite time+host queries
- `idx_traffic_host_status`: Host and status filtering
- `idx_traffic_time_status`: Time and status filtering

### 4. Configuration

#### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | npm-monitor-db | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | npm_monitor | Database name |
| `DB_USER` | npm_user | Database user |
| `DB_PASSWORD` | - | Database password (required) |
| `LOG_DIR` | /logs | Log directory path |
| `LINES_PER_FILE` | 10000 | Max lines per log file |
| `MAX_DISPLAY_ROWS` | 50000 | Max rows in dashboard |
| `RETENTION_DAYS` | 30 | Data retention period |
| `ENABLE_GEOIP` | false | Enable GeoIP lookup |
| `GEOIP_DB_PATH` | /geoip/GeoLite2-City.mmdb | GeoIP database path |
| `ENABLE_AUTH` | true | Enable authentication |
| `AUTH_USERNAME` | admin | Dashboard username |
| `AUTH_PASSWORD` | - | Dashboard password (required) |
| `ALLOWED_NETWORKS` | 127.0.0.1/32 | Allowed IP networks |

### 5. Authentication Flow

```
User Request → check_auth()
                  ↓
          check_ip_access() → IP in allowed networks?
                  ↓                    ↓
              Yes: Check session    No: Deny access
                  ↓
          Session exists?
           ↓        ↓
        Yes: Allow  No: Show login form
                        ↓
                   Validate credentials
                        ↓
                   Create session
```

### 6. Performance Optimizations

#### Caching Strategy
- **GeoIP Cache**: LRU cache with 1-hour TTL (4096 entries)
- **IP Filter Cache**: LRU cache for ignored IP checks
- **Streamlit Cache**: 30-60s TTL for dashboard data

#### Database Optimizations
- Connection pooling (min 1, max 10 connections)
- Composite indexes for common query patterns
- Batch inserts for log processing
- Query timeout (30s)

#### Thread Safety
- All caches use thread-safe locks
- Database connections use context managers
- Proper resource cleanup

### 7. Error Handling

#### Database Errors
- Automatic rollback on transaction failure
- Connection pool management
- Retry logic for transient errors

#### Log Parsing
- Graceful fallback for malformed lines
- Error logging without crashing
- Skip invalid entries

### 8. Security Considerations

#### Authentication
- Password-based authentication (configurable)
- IP-based network access control
- Session management via Streamlit

#### Data Protection
- Read-only access to log files
- No logging of sensitive data
- Prepared statements for SQL queries

#### Network Security
- Internal Docker network mode
- Port binding to specific interfaces
- TLS/HTTPS support via reverse proxy

## Development

### Running Tests
```bash
python3 -m pytest tests/ -v
```

### Database Migrations
- Automatic schema migration on startup
- Safe column addition with error handling
- Index creation with IF NOT EXISTS

### Adding New Features
1. Create feature module in `src/`
2. Add tests in `tests/`
3. Update documentation
4. Run tests before commit