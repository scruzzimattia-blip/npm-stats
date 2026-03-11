# Architecture Overview

## System Architecture

NPM Monitor is a web-based traffic analysis dashboard for Nginx Proxy Manager (NPM) logs. It follows a modular architecture with clear separation of concerns.

```
┌─────────────────────────────────────────────────────────────┐
│                      NPM Monitor                             │
│                                                               │
│  ┌──────────────┐      ┌──────────────┐                  │
│  │   Streamlit   │      │   Streamlit   │                  │
│  │   Dashboard   │──────│   Components  │                  │
│  │   (app.py)    │      │  (charts, etc)│                  │
│  └──────────────┘      └──────────────┘                  │
│         │                     │                              │
│         └──────────┬──────────┘                              │
│                    │                                          │
│         ┌──────────▼──────────┐                              │
│         │   Authentication     │                              │
│         │     (auth.py)         │                              │
│         └──────────┬──────────┘                              │
│                    │                                          │
│    ┌───────────────┼───────────────┐                        │
│    │               │               │                         │
│    ▼               ▼               ▼                         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│ │ Database │ │ Log      │ │ Sync     │                     │
│ │ Operations│ │ Parser   │ │ Scheduler│                     │
│ │(database)│ │(log_      │ │(sync_    │                     │
│ │          │ │parser)   │ │scheduler)│                     │
│ └────┬─────┘ └────┬─────┘ └────┬─────┘                     │
│      │            │            │                             │
│      └────────────┼────────────┘                             │
│                   │                                          │
│         ┌─────────▼─────────┐                               │
│         │  PostgreSQL DB    │                               │
│         │  (traffic table)   │                               │
│         └────────────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

## Component Description

### 1. Presentation Layer

#### Streamlit Dashboard (`app.py`)
- **Responsibility**: Main UI and user interaction
- **Features**:
  - Traffic visualization with charts and tables
  - Date range and host filtering
  - Real-time log synchronization
  - CSV export functionality

#### Components (`src/components/`)
- **charts.py**: Bandwidth, status codes, traffic trends
- **tables.py**: Top IPs, paths, referers
- **sidebar.py**: Filter controls and settings
- **Separation of Concerns**: Each component handles specific visualization

### 2. Business Logic Layer

#### Authentication (`auth.py`)
- **IP-based Access Control**: Whitelist/blacklist networks
- **Password Authentication**: Session-based login
- **Security**: Prevents unauthorized access

#### Log Synchronization (`sync.py`)
- **Parallel Processing**: ThreadPoolExecutor for log files
- **Incremental Updates**: Only new entries synced
- **Error Handling**: Graceful failure handling

#### Log Parsing (`log_parser.py`)
- **Pattern Matching**: Regex-based log line parsing
- **IP Filtering**: Private IPs, Cloudflare ranges
- **GeoIP Lookup**: Optional country/city resolution
- **Caching**: TTL-based LRU cache for performance

### 3. Data Access Layer

#### Database Operations (`database.py`)
- **Connection Pooling**: Efficient connection management
- **Batch Operations**: Bulk inserts for performance
- **Query Optimization**: Prepared statements, indexes
- **Data Retention**: Automatic cleanup of old records

## Data Flow

### Log Processing Pipeline
```
1. Log Files (NPM)
   ↓
2. File Discovery (sync.py)
   ↓
3. Parallel Parsing (log_parser.py)
   ↓
4. IP Filtering & GeoIP
   ↓
5. Batch Insert (database.py)
   ↓
6. PostgreSQL Storage
```

### Dashboard Data Flow
```
1. User Request (Streamlit)
   ↓
2. Authentication Check (auth.py)
   ↓
3. Database Query (database.py)
   ↓
4. Data Processing (pandas)
   ↓
5. Visualization (components)
   ↓
6. User Display (Streamlit)
```

## Database Design

### Traffic Table
- **Primary Key**: Auto-increment ID
- **Unique Constraint**: (time, host, remote_addr, path) prevents duplicates
- **Indexes**:
  - Time-based (DESC) for chronological queries
  - Host-based for domain filtering
  - Composite (host+status, time+status) for dashboard

### Query Patterns
```sql
-- Recent traffic
SELECT * FROM traffic 
WHERE time > NOW() - INTERVAL '7 days' 
ORDER BY time DESC;

-- Top hosts
SELECT host, COUNT(*) FROM traffic 
GROUP BY host ORDER BY COUNT(*) DESC;

-- Status codes
SELECT status, COUNT(*) FROM traffic 
WHERE host = ? GROUP BY status;
```

## Performance Optimizations

### 1. Database
- **Connection Pool**: Min 1, Max 10 connections
- **Batch Inserts**: 1000+ records per transaction
- **Indexes**: Optimized for dashboard query patterns
- **Vacuum**: Automatic cleanup

### 2. Caching
- **Streamlit Cache**: 30-60s TTL for dashboard data
- **GeoIP Cache**: 1-hour TTL for IP lookups
- **IP Filter Cache**: Memoized network checks

### 3. Parallelization
- **ThreadPoolExecutor**: 4 workers for log parsing
- **Batch Processing**: Chunked file reading
- **Async Operations**: Non-blocking sync

## Security Architecture

### Authentication Flow
```
Client → Streamlit → check_auth()
                        ↓
                 check_ip_access()
                        ↓
                 IP Allowed? → No → Deny
                        ↓ Yes
                 Session Valid? → No → Login Form
                        ↓ Yes
                 Allow Access
```

### Network Security
- **Docker Networks**: Internal-only communication
- **Port Binding**: Specific interfaces only
- **Read-Only Filesystem**: Container hardening
- **No New Privileges**: Security option

### Data Security
- **Prepared Statements**: SQL injection prevention
- **Input Validation**: Log line sanitization
- **No Secrets in Logs**: Safe error handling

## Deployment Architecture

### Docker Containers
```
geoip-updater (MaxMind)
       ↓
   GeoIP DB
       ↓
npm-monitor (Streamlit)
       ↓
PostgreSQL (External)
```

### Container Hardening
- **Non-root User**: `appuser` (UID 1000)
- **Read-only FS**: Except `/tmp` and `/home/appuser/.streamlit`
- **Resource Limits**: 1GB RAM, 1 CPU
- **Health Checks**: 30s interval
- **Security Options**: `no-new-privileges`

## Monitoring & Observability

### Health Checks
- **Database**: Connection test
- **Application**: Streamlit health endpoint
- **GeoIP**: Database availability

### Logging
- **Structured Logging**: JSON format
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Rotation**: 10MB max, 3 files

## Scalability Considerations

### Horizontal Scaling
- **Multiple Workers**: Streamlit supports threading
- **Load Balancer**: Reverse proxy for distribution
- **Shared Cache**: Redis for session/state

### Vertical Scaling
- **Connection Pool**: Increase max connections
- **Thread Pool**: More workers for parsing
- **Memory**: Adjust for data volume

### Database Scaling
- **Partitioning**: Time-based table partitioning
- **Read Replicas**: Separate read/write databases
- **Indexing**: Additional composite indexes

## Future Enhancements

### Planned Features
1. **Redis Integration**: Shared cache layer
2. **Prometheus Metrics**: Application metrics
3. **Alert System**: Threshold notifications
4. **API Endpoint**: RESTful data access
5. **Multi-tenancy**: Support multiple NPM instances

### Architecture Improvements
1. **Microservices**: Split sync and dashboard
2. **Event-Driven**: Kafka for log streaming
3. **GraphQL**: Flexible data queries
4. **Time-Series DB**: InfluxDB for metrics