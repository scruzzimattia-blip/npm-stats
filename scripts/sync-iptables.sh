#!/bin/bash
# NPM Monitor - iptables Sync Script
# Runs on HOST system to sync blocklist from database to iptables

set -e

# Configuration
DB_HOST="${DB_HOST:-shared-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-npm_monitor}"
DB_USER="${DB_USER:-npm_user}"
DB_PASSWORD="${DB_PASSWORD:-npm_monitor_password}"

# iptables chain name
CHAIN="NPM_MONITOR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Create iptables chain if it doesn't exist
create_chain() {
    if ! iptables -L "$CHAIN" -n >/dev/null 2>&1; then
        log "Creating iptables chain: $CHAIN"
        iptables -N "$CHAIN"
        iptables -I INPUT -j "$CHAIN"
        log "Chain created and added to INPUT"
    fi
}

# Get blocked IPs from database
get_blocked_ips() {
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT ip_address 
        FROM blocklist 
        WHERE unblocked_at IS NULL 
        AND block_until > NOW()
        ORDER BY blocked_at DESC;
    " 2>/dev/null | grep -v '^$' | sed 's/^[[:space:]]//;s/[[:space:]]$//'
}

# Sync IPs to iptables
sync_ips() {
    local current_ips
    local blocked_ips
    local to_add
    local to_remove
    
    # Get current IPs in iptables
    current_ips=$(iptables -L "$CHAIN" -n | grep DROP | awk '{print $4}' | sort -u)
    
    # Get blocked IPs from database
    blocked_ips=$(get_blocked_ips | sort -u)
    
    # IPs to add
    to_add=$(comm -13 <(echo "$current_ips") <(echo "$blocked_ips"))
    
    # IPs to remove
    to_remove=$(comm -23 <(echo "$current_ips") <(echo "$blocked_ips"))
    
    # Add new IPs
    if [ -n "$to_add" ]; then
        echo "$to_add" | while read -r ip; do
            if [ -n "$ip" ]; then
                log "Blocking IP: $ip"
                iptables -A "$CHAIN" -s "$ip" -j DROP -m comment --comment "npm-monitor"
            fi
        done
    fi
    
    # Remove unblocked IPs
    if [ -n "$to_remove" ]; then
        echo "$to_remove" | while read -r ip; do
            if [ -n "$ip" ]; then
                log "Unblocking IP: $ip"
                iptables -D "$CHAIN" -s "$ip" -j DROP -m comment --comment "npm-monitor" 2>/dev/null || true
            fi
        done
    fi
    
    log "Sync complete. Blocked IPs: $(echo "$blocked_ips" | wc -l)"
}

# Cleanup expired blocks from database
cleanup_database() {
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        UPDATE blocklist 
        SET unblocked_at = NOW() 
        WHERE unblocked_at IS NULL 
        AND block_until <= NOW();
    " >/dev/null 2>&1
}

# Main
main() {
    log "Starting NPM Monitor iptables sync"
    
    # Check if running as root
    if [ "$(id -u)" -ne 0 ]; then
        log "ERROR: This script must be run as root"
        exit 1
    fi
    
    # Create chain
    create_chain
    
    # Cleanup database
    cleanup_database
    
    # Sync IPs
    sync_ips
    
    log "Done"
}

# Run main
main "$@"