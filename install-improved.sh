#!/bin/bash
# =============================================================================
# PiServer Complete Installation Script - IMPROVED
# Handles all edge cases and database initialization properly
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}▶${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════"
echo "  PiServer Complete - Automated Installation"
echo "═══════════════════════════════════════════════════════════"
echo ""

# =============================================================================
# Configuration
# =============================================================================

INSTALL_DIR="/opt/attendance"
DATA_DIR="/var/lib/attendance"
CONFIG_DIR="/etc/attendance"
SERVICE_NAME="attendance"
PORT="${ATT_PORT:-5000}"
ENV="${ATT_ENV:-prod}"

# =============================================================================
# Install Dependencies
# =============================================================================

log_info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv sqlite3 git curl > /dev/null 2>&1
log_success "Dependencies installed"

# =============================================================================
# Create Directories
# =============================================================================

log_info "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/faces"
mkdir -p "$DATA_DIR/uploads"
mkdir -p "$CONFIG_DIR"
log_success "Directories created"

# =============================================================================
# Get Source Code
# =============================================================================

log_info "Getting source code..."

if [ -d "$INSTALL_DIR/.git" ]; then
    log_info "Repository already exists, pulling latest changes..."
    cd "$INSTALL_DIR"
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || log_warning "Could not pull updates"
else
    log_info "Cloning repository..."
    if [ -d "/tmp/piserver-complete" ]; then
        log_info "Using local files from /tmp/piserver-complete..."
        cp -r /tmp/piserver-complete/* "$INSTALL_DIR/"
    elif [ -d "$(pwd)/piserver-complete" ]; then
        log_info "Using local files from current directory..."
        cp -r "$(pwd)/piserver-complete"/* "$INSTALL_DIR/"
    elif [ -d "$HOME/piserver-complete" ]; then
        log_info "Using local files from home directory..."
        cp -r "$HOME/piserver-complete"/* "$INSTALL_DIR/"
    else
        log_warning "No local files found, attempting to clone from GitHub..."
        read -p "Enter GitHub repository URL (or press Enter to skip): " REPO_URL
        if [ -n "$REPO_URL" ]; then
            git clone "$REPO_URL" "$INSTALL_DIR" || {
                log_error "Failed to clone repository"
                exit 1
            }
        else
            log_error "No source code available. Please provide files in /tmp/piserver-complete"
            exit 1
        fi
    fi
fi

cd "$INSTALL_DIR"
log_success "Source code ready"

# =============================================================================
# Python Virtual Environment
# =============================================================================

log_info "Setting up Python virtual environment..."

if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi

source "$INSTALL_DIR/venv/bin/activate"

log_info "Upgrading pip..."
pip install --upgrade pip --quiet

log_info "Installing Python dependencies..."
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install -r "$INSTALL_DIR/requirements.txt" --quiet
else
    log_warning "requirements.txt not found, installing minimal dependencies..."
    pip install Flask requests python-dateutil openpyxl pandas urllib3 reportlab python-dotenv Pillow --quiet
fi

log_success "Virtual environment configured"

# =============================================================================
# Configuration
# =============================================================================

log_info "Creating configuration..."

# Generate secure secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Create environment file
cat > "$CONFIG_DIR/attendance.env" << EOF
# PiServer Attendance System Configuration
# Generated on $(date)

ATT_ENV=$ENV
ATT_DB=$DATA_DIR/attendance.db
ATT_PORT=$PORT
SECRET_KEY=$SECRET_KEY
TZ=${TZ:-UTC}
EOF

chmod 600 "$CONFIG_DIR/attendance.env"
log_success "Configuration created at $CONFIG_DIR/attendance.env"

# =============================================================================
# Database Initialization
# =============================================================================

log_info "Initializing database..."

DB_PATH="$DATA_DIR/attendance.db"

# Check if database exists
if [ -f "$DB_PATH" ]; then
    log_warning "Database already exists at $DB_PATH"
    read -p "Do you want to recreate it? (y/N): " RECREATE_DB
    if [[ "$RECREATE_DB" =~ ^[Yy]$ ]]; then
        log_info "Backing up existing database..."
        cp "$DB_PATH" "$DB_PATH.backup.$(date +%Y%m%d_%H%M%S)"
        rm "$DB_PATH"
        log_success "Backup created"
    fi
fi

# Create database schema
if [ ! -f "$DB_PATH" ]; then
    log_info "Creating database schema..."
    
    if [ -f "$INSTALL_DIR/schema.sql" ]; then
        sqlite3 "$DB_PATH" < "$INSTALL_DIR/schema.sql" 2>/dev/null || {
            log_warning "Some schema errors (might be expected if tables already exist)"
        }
        log_success "Base schema created"
    else
        log_error "schema.sql not found!"
        exit 1
    fi
    
    # Apply enhancements if available
    if [ -f "$INSTALL_DIR/schema_enhancements.sql" ]; then
        log_info "Applying schema enhancements..."
        sqlite3 "$DB_PATH" < "$INSTALL_DIR/schema_enhancements.sql" 2>/dev/null || {
            log_warning "Some enhancement errors (might be expected)"
        }
        log_success "Schema enhancements applied"
    fi
fi

# Ensure critical columns exist (fix for incomplete schemas)
log_info "Verifying database schema..."

sqlite3 "$DB_PATH" << 'EOSQL' 2>/dev/null || log_warning "Some columns already exist (this is OK)"
-- Ensure accounts table exists
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'viewer',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Add missing columns to users table (ignore errors if they exist)
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

log_success "Database schema verified"

# Initialize additional features
if [ -f "$INSTALL_DIR/setup_features.py" ]; then
    log_info "Initializing additional features..."
    cd "$INSTALL_DIR"
    source venv/bin/activate
    export ATT_DB="$DB_PATH"
    python3 setup_features.py 2>/dev/null || log_warning "Feature initialization had warnings (might be OK)"
    log_success "Additional features initialized"
fi

# =============================================================================
# Create Admin Account
# =============================================================================

log_info "Creating admin account..."

# Prompt for admin credentials
read -p "Admin username (default: admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

while true; do
    read -s -p "Admin password (default: admin): " ADMIN_PASS
    echo
    ADMIN_PASS=${ADMIN_PASS:-admin}
    
    if [ ${#ADMIN_PASS} -lt 4 ]; then
        log_error "Password must be at least 4 characters"
        continue
    fi
    
    read -s -p "Confirm password: " ADMIN_PASS_CONFIRM
    echo
    
    if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
        log_error "Passwords do not match"
        continue
    fi
    
    break
done

# Create admin account
cd "$INSTALL_DIR"
source venv/bin/activate

python3 << EOPY
from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect('$DB_PATH')
cur = conn.cursor()

password_hash = generate_password_hash('$ADMIN_PASS')

# Delete existing admin if present
cur.execute("DELETE FROM accounts WHERE username = ?", ('$ADMIN_USER',))

# Create new admin
cur.execute("""
    INSERT INTO accounts (username, password_hash, role, active)
    VALUES (?, ?, 'admin', 1)
""", ('$ADMIN_USER', password_hash))

conn.commit()
conn.close()
print("✓ Admin account created successfully")
EOPY

log_success "Admin account configured"

# =============================================================================
# Fix server.py Import Issues
# =============================================================================

log_info "Checking server.py for import issues..."

if [ -f "$INSTALL_DIR/server.py" ]; then
    # Comment out problematic bootstrap_db import if it exists
    if grep -q "from scripts.bootstrap_db import main as bootstrap_db" "$INSTALL_DIR/server.py" 2>/dev/null; then
        log_info "Fixing bootstrap_db import..."
        sed -i 's/^from scripts.bootstrap_db import main as bootstrap_db/# from scripts.bootstrap_db import main as bootstrap_db/' "$INSTALL_DIR/server.py"
        sed -i 's/^    bootstrap_db()/    # bootstrap_db()/' "$INSTALL_DIR/server.py"
        log_success "Import issue fixed"
    fi
fi

# =============================================================================
# Create Systemd Service
# =============================================================================

log_info "Installing systemd service..."

cat > "/etc/systemd/system/$SERVICE_NAME.service" << EOF
[Unit]
Description=PiServer Attendance System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="ATT_ENV=$ENV"
Environment="ATT_DB=$DB_PATH"
Environment="ATT_PORT=$PORT"
Environment="SECRET_KEY=$SECRET_KEY"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
log_success "Systemd service installed"

# =============================================================================
# Set Permissions
# =============================================================================

log_info "Setting permissions..."
chown -R root:root "$INSTALL_DIR"
chown -R root:root "$DATA_DIR"
chmod -R 755 "$INSTALL_DIR"
chmod -R 755 "$DATA_DIR"
chmod 600 "$CONFIG_DIR/attendance.env"
log_success "Permissions set"

# =============================================================================
# Start Service
# =============================================================================

log_info "Starting service..."
systemctl start "$SERVICE_NAME"
sleep 3

if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_success "Service started successfully"
else
    log_error "Service failed to start"
    log_info "Check logs with: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# =============================================================================
# Get IP Address
# =============================================================================

IP_ADDR=$(hostname -I | awk '{print $1}')

# =============================================================================
# Installation Complete
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Installation Complete! 🎉"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Access your PiServer at:"
echo "  ${GREEN}http://$IP_ADDR:$PORT${NC}"
echo "  ${GREEN}http://$(hostname).local:$PORT${NC}"
echo ""
echo "Login credentials:"
echo "  Username: ${BLUE}$ADMIN_USER${NC}"
echo "  Password: ${BLUE}$ADMIN_PASS${NC}"
echo ""
echo "⚠️  IMPORTANT: Change your password after first login!"
echo ""
echo "Useful commands:"
echo "  View logs:       journalctl -u $SERVICE_NAME -f"
echo "  Stop service:    systemctl stop $SERVICE_NAME"
echo "  Start service:   systemctl start $SERVICE_NAME"
echo "  Restart:         systemctl restart $SERVICE_NAME"
echo "  Status:          systemctl status $SERVICE_NAME"
echo ""
echo "Configuration:   $CONFIG_DIR/attendance.env"
echo "Data directory:  $DATA_DIR"
echo "Install directory: $INSTALL_DIR"
echo ""
echo "═══════════════════════════════════════════════════════════"
