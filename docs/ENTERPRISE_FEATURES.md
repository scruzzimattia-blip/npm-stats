# NPM Monitor Enterprise Features

This document provides in-depth information about the advanced security and maintenance features introduced in the Enterprise Edition (v2.0.0+).

---

## 1. Deceptive Defense (Enterprise Honeypots)
Unlike regular "Suspicious Paths" which contribute to a score, **Honey-Paths** are high-value bait targets.

### How it works
Any request to a defined Honey-Path triggers an **immediate 1-year ban** across all defense layers (App, Firewall, Cloudflare).

### Default Bait Paths
- `/.env`, `/.git`
- `/wp-config.php`, `/config.php`
- `/phpmyadmin`, `/pma`, `/myadmin`
- `/.aws/credentials`, `/.ssh/id_rsa`

---

## 2. AI-Powered Daily Briefings
The system now features an autonomous AI task that runs every 24 hours to give the administrator a high-level overview.

### Features
- **Trend Analysis**: Compares today's traffic with the previous 24 hours.
- **Threat Identification**: Groups malicious IPs by behavior (e.g., "Botnet scanning from ASN 123").
- **Proactive Rules**: Suggests new paths to add to the blocklist based on 404 patterns.

---

## 3. High-Performance Caching (Redis)
To handle enterprise-grade traffic loads, ephemeral tracking state has been moved from PostgreSQL to **Redis**.

### Benefits
- **Sub-millisecond Tracking**: IP counters and rate-limit buckets are updated in memory.
- **DB Offloading**: Reduces PostgreSQL write-load by over 90%.
- **Atomic Operations**: Prevents race conditions during high-volume DDoS attacks.

---

## 4. Automated Log Archiving
Instead of simply deleting old logs, the Enterprise Edition preserves history while keeping the database lean.

### Process
1. During the daily cleanup, logs older than `RETENTION_DAYS` are selected.
2. The data is exported to a compressed CSV file (`.csv.gz`) in the `archives/` directory.
3. Only after a successful export is the data removed from the live `traffic` table.

---

## 5. Visual Observability (Live Monitor)
The new Live Monitor provides real-time insights beyond static charts.

### Network Graph
Visualizes connections using Graphviz:
- **Red Nodes**: Malicious/Blocked IPs.
- **Blue Nodes**: Normal Traffic.
- **Edges**: Represent requests to specific hosts and paths with their HTTP status.
