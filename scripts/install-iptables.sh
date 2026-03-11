#!/bin/bash
# NPM Monitor - iptables Installation Script
# Installs host-based iptables blocking on the host system

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        error "This script must be run as root. Use: sudo $0"
    fi
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    if ! command -v iptables &> /dev/null; then
        error "iptables not found. Please install: apt-get install iptables"
    fi
    
    if ! command -v psql &> /dev/null; then
        warn "PostgreSQL client not found. Installing..."
        apt-get update
        apt-get install -y postgresql-client
    fi
    
    log "Dependencies OK"
}

# Install script
install_script() {
    log "Installing sync script..."
    
    # Copy script
    cp "$(dirname "$0")/sync-iptables.sh" /usr/local/bin/npm-monitor-iptables.sh
    chmod +x /usr/local/bin/npm-monitor-iptables.sh
    
    log "Script installed to /usr/local/bin/npm-monitor-iptables.sh"
}

# Create configuration
create_config() {
    log "Creating configuration..."
    
    mkdir -p /etc/npm-monitor
    
    # Check if config exists
    if [ -f /etc/npm-monitor/iptables-sync.conf ]; then
        warn "Configuration file already exists. Skipping..."
        return
    fi
    
    # Prompt for database credentials
    echo ""
    echo "Please enter your NPM Monitor database credentials:"
    echo ""
    
    read -p "Database Host [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}
    
    read -p "Database Port [5432]: " DB_PORT
    DB_PORT=${DB_PORT:-5432}
    
    read -p "Database Name [npm_monitor]: " DB_NAME
    DB_NAME=${DB_NAME:-npm_monitor}
    
    read -p "Database User [npm_user]: " DB_USER
    DB_USER=${DB_USER:-npm_user}
    
    read -sp "Database Password: " DB_PASSWORD
    echo ""
    
    # Write config
    tee /etc/npm-monitor/iptables-sync.conf > /dev/null <<EOF
# NPM Monitor iptables Sync Configuration
# Generated on $(date)

# Database connection
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
EOF
    
    chmod 600 /etc/npm-monitor/iptables-sync.conf
    
    log "Configuration created at /etc/npm-monitor/iptables-sync.conf"
}

# Install systemd service
install_systemd() {
    log "Installing systemd service..."
    
    # Copy service file
    tee /etc/systemd/system/npm-monitor-iptables.service > /dev/null <<'EOF'
[Unit]
Description=NPM Monitor iptables Sync Service
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/npm-monitor-iptables.sh
User=root
Group=root
EnvironmentFile=/etc/npm-monitor/iptables-sync.conf

[Install]
WantedBy=multi-user.target
EOF
    
    # Copy timer file
    tee /etc/systemd/system/npm-monitor-iptables.timer > /dev/null <<'EOF'
[Unit]
Description=NPM Monitor iptables Sync Timer
After=network.target postgresql.service

[Timer]
OnCalendar=*:0/1:*
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    log "Systemd service installed"
}

# Test database connection
test_database() {
    log "Testing database connection..."
    
    source /etc/npm-monitor/iptables-sync.conf
    
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        log "Database connection: OK"
    else
        error "Cannot connect to database. Check your credentials."
    fi
}

# Test iptables
test_iptables() {
    log "Testing iptables..."
    
    # Create test chain
    if ! iptables -L NPM_MONITOR -n > /dev/null 2>&1; then
        iptables -N NPM_MONITOR
        iptables -I INPUT -j NPM_MONITOR
        log "iptables chain created"
    else
        log "iptables chain already exists"
    fi
    
    # Test adding/removing rule
    iptables -A NPM_MONITOR -s 127.0.0.1 -j DROP -m comment --comment "test"
    iptables -D NPM_MONITOR -s 127.0.0.1 -j DROP -m comment --comment "test"
    
    log "iptables: OK"
}

# Enable and start service
enable_service() {
    log "Enabling systemd timer..."
    
    systemctl enable npm-monitor-iptables.timer
    systemctl start npm-monitor-iptables.timer
    
    log "Service started and enabled"
}

# Show status
show_status() {
    echo ""
    log "=== Installation Complete ==="
    echo ""
    log "Configuration: /etc/npm-monitor/iptables-sync.conf"
    log "Script: /usr/local/bin/npm-monitor-iptables.sh"
    log "Service: npm-monitor-iptables.timer"
    echo ""
    log "Useful commands:"
    echo "  sudo systemctl status npm-monitor-iptables.timer"
    echo "  sudo journalctl -u npm-monitor-iptables -f"
    echo "  sudo iptables -L NPM_MONITOR -n -v"
    echo "  sudo /usr/local/bin/npm-monitor-iptables.sh"
    echo ""
}

# Main installation
main() {
    log "=== NPM Monitor iptables Installer ==="
    echo ""
    
    check_root
    check_dependencies
    install_script
    create_config
    install_systemd
    test_database
    test_iptables
    enable_service
    show_status
    
    log "Installation successful!"
}

# Run main
main "$@"