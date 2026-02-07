#!/usr/bin/env bash
# =============================================================================
# PiServer Attendance System - Universal Installer
# =============================================================================
# Supports: Ubuntu/Debian, CentOS/RHEL, macOS, Docker
# Usage: curl -sSL https://raw.githubusercontent.com/stujoubert/PiServer/main/install.sh | bash
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/attendance"
DATA_DIR="/var/lib/attendance"
CONFIG_DIR="/etc/attendance"
SERVICE_NAME="attendance"
GITHUB_REPO="https://github.com/stujoubert/PiServer.git"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}   PiServer Attendance System - Installer${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS=$ID
            OS_VERSION=$VERSION_ID
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    print_step "Detected OS: $OS"
}

check_requirements() {
    print_step "Checking requirements..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    # Check for required commands
    for cmd in git python3 sqlite3; do
        if ! command -v $cmd &> /dev/null; then
            print_warning "$cmd not found, will be installed"
        else
            print_success "$cmd found"
        fi
    done
}

install_dependencies() {
    print_step "Installing system dependencies..."
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get update
        apt-get install -y python3 python3-venv python3-pip git sqlite3 curl
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]]; then
        yum install -y python3 python3-pip git sqlite curl
    elif [[ "$OS" == "macos" ]]; then
        if ! command -v brew &> /dev/null; then
            print_error "Homebrew not found. Please install from https://brew.sh"
            exit 1
        fi
        brew install python3 git sqlite3
    fi
    
    print_success "Dependencies installed"
}

create_directories() {
    print_step "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR/faces"
    mkdir -p "$CONFIG_DIR"
    
    print_success "Directories created"
}

clone_repository() {
    print_step "Cloning repository..."
    
    if [ -d "$INSTALL_DIR/.git" ]; then
        print_warning "Repository already exists, pulling latest changes..."
        cd "$INSTALL_DIR"
        git pull
    else
        git clone "$GITHUB_REPO" "$INSTALL_DIR"
    fi
    
    print_success "Repository cloned"
}

setup_virtualenv() {
    print_step "Setting up Python virtual environment..."
    
    cd "$INSTALL_DIR"
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    
    print_success "Virtual environment configured"
}

create_config() {
    print_step "Creating configuration..."
    
    # Generate random secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    
    # Prompt for configuration
    read -p "Enter port number (default: 5000): " PORT
    PORT=${PORT:-5000}
    
    read -p "Environment (prod/dev, default: prod): " ENV
    ENV=${ENV:-prod}
    
    cat > "$CONFIG_DIR/attendance.env" <<EOF
# PiServer Attendance Configuration
# Generated on $(date)

# Environment
ATT_ENV=$ENV
ATT_DB=$DATA_DIR/attendance.db
ATT_PORT=$PORT

# Security
SECRET_KEY=$SECRET_KEY

# Timezone
TZ=$(cat /etc/timezone 2>/dev/null || echo "UTC")
EOF
    
    chmod 600 "$CONFIG_DIR/attendance.env"
    print_success "Configuration created at $CONFIG_DIR/attendance.env"
}

install_systemd_service() {
    print_step "Installing systemd service..."
    
    cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=PiServer Attendance System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_DIR/attendance.env
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    
    print_success "Systemd service installed"
}

create_admin_account() {
    print_step "Creating admin account..."
    
    read -p "Enter admin username (default: admin): " ADMIN_USER
    ADMIN_USER=${ADMIN_USER:-admin}
    
    read -sp "Enter admin password: " ADMIN_PASS
    echo
    
    # Hash password and insert into database
    cd "$INSTALL_DIR"
    source venv/bin/activate
    python3 <<EOF
from werkzeug.security import generate_password_hash
import sqlite3
import os

db_path = os.environ.get('ATT_DB', '$DATA_DIR/attendance.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create accounts table if not exists
cur.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','manager','viewer')),
        active INTEGER NOT NULL DEFAULT 1
    )
''')

# Insert admin account
password_hash = generate_password_hash('$ADMIN_PASS')
try:
    cur.execute(
        "INSERT INTO accounts (username, password_hash, role) VALUES (?, ?, ?)",
        ('$ADMIN_USER', password_hash, 'admin')
    )
    conn.commit()
    print("Admin account created successfully")
except sqlite3.IntegrityError:
    print("Admin account already exists")
finally:
    conn.close()
EOF
    
    print_success "Admin account configured"
}

start_service() {
    print_step "Starting service..."
    
    systemctl start $SERVICE_NAME
    sleep 3
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_success "Service started successfully"
    else
        print_error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME"
        exit 1
    fi
}

print_completion() {
    echo
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   Installation Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo
    echo -e "Access the application at: ${BLUE}http://localhost:$PORT${NC}"
    echo
    echo "Useful commands:"
    echo "  • View logs:    journalctl -u $SERVICE_NAME -f"
    echo "  • Stop service: systemctl stop $SERVICE_NAME"
    echo "  • Start service: systemctl start $SERVICE_NAME"
    echo "  • Restart:      systemctl restart $SERVICE_NAME"
    echo "  • Status:       systemctl status $SERVICE_NAME"
    echo
    echo "Configuration file: $CONFIG_DIR/attendance.env"
    echo "Data directory:     $DATA_DIR"
    echo
}

# =============================================================================
# Main Installation Flow
# =============================================================================

main() {
    print_header
    detect_os
    check_requirements
    install_dependencies
    create_directories
    clone_repository
    setup_virtualenv
    create_config
    
    # Only install systemd service on Linux
    if [[ "$OS" != "macos" ]]; then
        install_systemd_service
    fi
    
    create_admin_account
    
    # Only start service on Linux with systemd
    if [[ "$OS" != "macos" ]]; then
        start_service
    else
        print_warning "Manual start required on macOS:"
        echo "  cd $INSTALL_DIR"
        echo "  source venv/bin/activate"
        echo "  source $CONFIG_DIR/attendance.env"
        echo "  python server.py"
    fi
    
    print_completion
}

# Run installation
main
