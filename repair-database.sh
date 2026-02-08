#!/bin/bash
# =============================================================================
# PiServer Database Repair Script
# Fixes common database schema issues
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}▶${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════"
echo "  PiServer Database Repair Script"
echo "═══════════════════════════════════════════════════════════"
echo ""

DB_PATH="${ATT_DB:-/var/lib/attendance/attendance.db}"

if [ ! -f "$DB_PATH" ]; then
    log_error "Database not found at $DB_PATH"
    exit 1
fi

log_info "Database: $DB_PATH"

# Backup database
BACKUP_PATH="$DB_PATH.backup.$(date +%Y%m%d_%H%M%S)"
log_info "Creating backup..."
cp "$DB_PATH" "$BACKUP_PATH"
log_success "Backup created: $BACKUP_PATH"

# Fix accounts table
log_info "Checking accounts table..."
sqlite3 "$DB_PATH" << 'EOSQL'
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'viewer',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
EOSQL
log_success "Accounts table verified"

# Fix users table columns
log_info "Adding missing columns to users table..."

sqlite3 "$DB_PATH" << 'EOSQL' 2>&1 | grep -v "duplicate column name" | grep -v "Error:" || true
ALTER TABLE users ADD COLUMN name TEXT;
ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1;
ALTER TABLE users ADD COLUMN department_id INTEGER;
ALTER TABLE users ADD COLUMN job_title TEXT;
ALTER TABLE users ADD COLUMN employee_type TEXT DEFAULT 'full-time';
ALTER TABLE users ADD COLUMN hire_date TEXT;
ALTER TABLE users ADD COLUMN supervisor_employee_id TEXT;
ALTER TABLE users ADD COLUMN overtime_policy_id INTEGER;
EOSQL

log_success "Users table columns updated"

# Verify critical tables exist
log_info "Verifying critical tables..."

TABLES="users accounts settings events devices schedules"
for table in $TABLES; do
    if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" | grep -q "$table"; then
        log_success "Table '$table' exists"
    else
        log_warning "Table '$table' missing"
    fi
done

# Show table structure
log_info "Users table structure:"
sqlite3 "$DB_PATH" "PRAGMA table_info(users);" | while read line; do
    echo "  $line"
done

log_info "Accounts table structure:"
sqlite3 "$DB_PATH" "PRAGMA table_info(accounts);" | while read line; do
    echo "  $line"
done

# Check for admin account
log_info "Checking admin account..."
ADMIN_EXISTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM accounts WHERE username='admin';" 2>/dev/null || echo "0")

if [ "$ADMIN_EXISTS" -eq "0" ]; then
    log_warning "No admin account found"
    read -p "Create admin account? (Y/n): " CREATE_ADMIN
    
    if [[ ! "$CREATE_ADMIN" =~ ^[Nn]$ ]]; then
        read -p "Admin username (default: admin): " ADMIN_USER
        ADMIN_USER=${ADMIN_USER:-admin}
        
        read -s -p "Admin password: " ADMIN_PASS
        echo
        
        cd /opt/attendance 2>/dev/null || cd ~
        
        if [ -f "venv/bin/activate" ]; then
            source venv/bin/activate
        fi
        
        python3 << EOPY
from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect('$DB_PATH')
cur = conn.cursor()

password_hash = generate_password_hash('$ADMIN_PASS')
cur.execute("INSERT INTO accounts (username, password_hash, role, active) VALUES (?, ?, 'admin', 1)", ('$ADMIN_USER', password_hash))
conn.commit()
conn.close()
print("✓ Admin account created")
EOPY
        
        log_success "Admin account created: $ADMIN_USER"
    fi
else
    log_success "Admin account exists"
fi

# Restart service if running
if systemctl is-active --quiet attendance; then
    log_info "Restarting attendance service..."
    systemctl restart attendance
    sleep 2
    if systemctl is-active --quiet attendance; then
        log_success "Service restarted successfully"
    else
        log_error "Service failed to restart"
        log_info "Check logs: journalctl -u attendance -n 50"
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Repair Complete!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Backup saved to: $BACKUP_PATH"
echo ""
log_success "Database repaired successfully"
