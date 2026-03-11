# NPM Monitor - Host iptables Integration

This guide explains how to set up firewall-level IP blocking on the **host system**.

## Overview

Instead of running iptables inside the Docker container (which requires root privileges), we run a script on the host that:
1. Reads blocked IPs from the NPM Monitor database
2. Creates iptables rules on the host
3. Runs periodically via systemd timer

## Installation

### 1. Install Dependencies

```bash
# Install PostgreSQL client
sudo apt-get update
sudo apt-get install -y postgresql-client iptables
```

### 2. Create Configuration File

```bash
# Create config directory
sudo mkdir -p /etc/npm-monitor

# Create environment file
sudo tee /etc/npm-monitor/iptables-sync.conf > /dev/null <<EOF
# Database connection (use your actual credentials)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=npm_monitor
DB_USER=npm_user
DB_PASSWORD=your_secure_password
EOF

# Set permissions
sudo chmod 600 /etc/npm-monitor/iptables-sync.conf
sudo chown root:root /etc/npm-monitor/iptables-sync.conf
```

### 3. Install Sync Script

```bash
# Copy script
sudo cp scripts/sync-iptables.sh /usr/local/bin/npm-monitor-sync-iptables.sh
sudo chmod +x /usr/local/bin/npm-monitor-sync-iptables.sh
```

### 4. Install Systemd Service

```bash
# Copy systemd service files
sudo cp scripts/npm-monitor-iptables.service /etc/systemd/system/
sudo cp scripts/npm-monitor-iptables.timer /etc/systemd/system/ 2>/dev/null || true

# Or create timer directly
sudo tee /etc/systemd/system/npm-monitor-iptables.timer > /dev/null <<EOF
[Unit]
Description=Run NPM Monitor iptables sync every minute

[Timer]
OnCalendar=*:*:0
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timer
sudo systemctl enable npm-monitor-iptables.timer
sudo systemctl start npm-monitor-iptables.timer
```

### 5. Test Manually

```bash
# Run manually to test
sudo /usr/local/bin/npm-monitor-sync-iptables.sh

# Check iptables rules
sudo iptables -L NPM_MONITOR -n -v
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | npm_monitor | Database name |
| `DB_USER` | npm_user | Database user |
| `DB_PASSWORD` | - | Database password (required) |

### Timing

The script runs every minute via systemd timer. To change:

```bash
# Edit timer
sudo systemctl edit npm-monitor-iptables.timer

# Set different interval (e.g., every 5 minutes)
[Timer]
OnCalendar=*:0/5:0

# Restart timer
sudo systemctl restart npm-monitor-iptables.timer
```

## How It Works

1. **Application Level**: NPM Monitor blocks IPs in the database
2. **Sync Script**: Reads blocked IPs from database
3. **iptables**: Creates DROP rules on host
4. **Automatic Cleanup**: Removes expired blocks

### Flowchart

```
NPM Container          Host System
    |                      |
    v                      |
Database (blocklist)      |
    |                      |
    +--------------------->|
         Sync Script       |
              |            |
              v            |
          iptables rules   |
              |            |
              v            |
        Host Firewall      |
```

## Manual Operations

### Check Blocked IPs

```bash
# View all blocked IPs
sudo iptables -L NPM_MONITOR -n -v

# Count blocked IPs
sudo iptables -L NPM_MONITOR -n | grep DROP | wc -l
```

### Manual Block/Unblock

```bash
# Block IP manually
sudo iptables -A NPM_MONITOR -s 192.168.1.100 -j DROP -m comment --comment "manual"

# Unblock IP manually
sudo iptables -D NPM_MONITOR -s 192.168.1.100 -j DROP

# Clear all rules
sudo iptables -F NPM_MONITOR
```

### Debug

```bash
# Check logs
sudo journalctl -u npm-monitor-iptables -f

# Test database connection
PGPASSWORD=your_password psql -h localhost -U npm_user -d npm_monitor -c "SELECT * FROM blocklist LIMIT 5;"
```

## Security Considerations

1. **Root Access**: Script runs as root, only install on trusted systems
2. **Database Access**: Use read-only database user if possible
3. **Network Access**: Script needs network access to database
4. **Log Files**: Check logs regularly for suspicious activity

## Troubleshooting

### Issue: iptables chain not created

```bash
# Manually create chain
sudo iptables -N NPM_MONITOR
sudo iptables -I INPUT -j NPM_MONITOR
```

### Issue: Cannot connect to database

```bash
# Check if PostgreSQL allows connections
telnet DB_HOST DB_PORT

# Check pg_hba.conf
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep npm_user
```

### Issue: iptables rules not persisting

```bash
# Install iptables-persistent
sudo apt-get install -y iptables-persistent

# Save rules
sudo iptables-save > /etc/iptables/rules.v4
```

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop npm-monitor-iptables.timer
sudo systemctl disable npm-monitor-iptables.timer

# Remove files
sudo rm /usr/local/bin/npm-monitor-sync-iptables.sh
sudo rm /etc/systemd/system/npm-monitor-iptables.*
sudo rm -rf /etc/npm-monitor

# Flush iptables chain
sudo iptables -F NPM_MONITOR
sudo iptables -D INPUT -j NPM_MONITOR
sudo iptables -X NPM_MONITOR

# Reload systemd
sudo systemctl daemon-reload
```

## Alternative: fail2ban Integration

Instead of direct iptables, you can use fail2ban:

1. NPM Monitor writes blocked IPs to `/var/log/npm-blocks.log`
2. fail2ban reads the log and creates iptables rules
3. More compatible with existing fail2ban setups

See `scripts/fail2ban/` for configuration files.