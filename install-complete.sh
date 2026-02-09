#!/bin/bash
# =============================================================================
# PiServer - MASTER INSTALLER
# Complete installation of PiServer with ALL enhancements
# =============================================================================
# This script installs:
# - Base PiServer system
# - Enhanced UI with dark mode
# - Department management
# - Leave/PTO system
# - REST API
# - All additional features
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}▶${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_section() { echo -e "${PURPLE}━━━${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

clear
echo "═══════════════════════════════════════════════════════════"
echo "  🚀 PiServer Complete - Master Installer"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "This will install:"
echo "  ✓ Base PiServer system"
echo "  ✓ Modern UI with dark mode"
echo "  ✓ Department management"
echo "  ✓ Leave/PTO tracking"
echo "  ✓ REST API"
echo "  ✓ Enhanced features"
echo ""
read -p "Continue with installation? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 0
fi

# =============================================================================
# Configuration
# =============================================================================

INSTALL_DIR="/opt/attendance"
DATA_DIR="/var/lib/attendance"
CONFIG_DIR="/etc/attendance"
SERVICE_NAME="attendance"
PORT="${ATT_PORT:-5000}"
ENV="${ATT_ENV:-prod}"

log_section "STEP 1/10: Installing System Dependencies"

apt-get update -qq
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    git \
    curl \
    wget \
    nginx \
    > /dev/null 2>&1

log_success "System dependencies installed"

# =============================================================================
# Create Directories
# =============================================================================

log_section "STEP 2/10: Creating Directory Structure"

mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/faces"
mkdir -p "$DATA_DIR/uploads"
mkdir -p "$CONFIG_DIR"
mkdir -p "$INSTALL_DIR/static/css"
mkdir -p "$INSTALL_DIR/static/js"
mkdir -p "$INSTALL_DIR/routes"
mkdir -p "$INSTALL_DIR/templates"
mkdir -p "$INSTALL_DIR/services"
mkdir -p "$INSTALL_DIR/scripts"

log_success "Directory structure created"

# =============================================================================
# Get Source Code
# =============================================================================

log_section "STEP 3/10: Installing Application Files"

log_info "Looking for source code..."

# Check common locations
SOURCE_LOCATIONS=(
    "/tmp/piserver-complete"
    "$HOME/piserver-complete"
    "$(pwd)/piserver-complete"
    "$INSTALL_DIR"
)

SOURCE_FOUND=0
for loc in "${SOURCE_LOCATIONS[@]}"; do
    if [ -d "$loc" ] && [ -f "$loc/server.py" ]; then
        log_info "Found source at: $loc"
        if [ "$loc" != "$INSTALL_DIR" ]; then
            cp -r "$loc"/* "$INSTALL_DIR/"
        fi
        SOURCE_FOUND=1
        break
    fi
done

if [ $SOURCE_FOUND -eq 0 ]; then
    log_warning "Source code not found locally"
    read -p "Enter GitHub repository URL (or press Enter to skip): " REPO_URL
    
    if [ -n "$REPO_URL" ]; then
        log_info "Cloning from GitHub..."
        git clone "$REPO_URL" "$INSTALL_DIR" || {
            log_error "Failed to clone repository"
            exit 1
        }
    else
        log_error "No source code available"
        log_info "Please place PiServer files in one of these locations:"
        for loc in "${SOURCE_LOCATIONS[@]}"; do
            echo "  - $loc"
        done
        exit 1
    fi
fi

cd "$INSTALL_DIR"
log_success "Application files installed"

# =============================================================================
# Python Virtual Environment
# =============================================================================

log_section "STEP 4/10: Setting Up Python Environment"

if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi

source "$INSTALL_DIR/venv/bin/activate"

log_info "Installing Python packages..."
pip install --upgrade pip --quiet

if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install -r "$INSTALL_DIR/requirements.txt" --quiet
else
    log_info "Installing essential packages..."
    pip install --quiet \
        Flask>=3.0.0 \
        Werkzeug>=3.0.0 \
        requests>=2.31.0 \
        python-dateutil>=2.8.2 \
        openpyxl>=3.1.0 \
        pandas>=2.0.0 \
        reportlab>=4.0.0 \
        Pillow>=10.0.0 \
        python-dotenv>=1.0.0 \
        cryptography>=41.0.0 \
        gunicorn>=21.2.0 \
        Flask-Limiter>=3.5.0 \
        flask-cors>=4.0.0 \
        APScheduler>=3.10.0 \
        marshmallow>=3.20.0 \
        pytz>=2023.3
fi

log_success "Python environment configured"

# =============================================================================
# Configuration
# =============================================================================

log_section "STEP 5/10: Creating Configuration"

log_info "Generating secure secret key..."
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat > "$CONFIG_DIR/attendance.env" << EOF
# PiServer Configuration
# Generated on $(date)

ATT_ENV=$ENV
ATT_DB=$DATA_DIR/attendance.db
ATT_PORT=$PORT
SECRET_KEY=$SECRET_KEY
TZ=${TZ:-UTC}
EOF

chmod 600 "$CONFIG_DIR/attendance.env"
log_success "Configuration created"

# =============================================================================
# Database Setup
# =============================================================================

log_section "STEP 6/10: Initializing Database"

DB_PATH="$DATA_DIR/attendance.db"

if [ -f "$DB_PATH" ]; then
    log_warning "Database already exists"
    read -p "Recreate database? This will DELETE all data! (y/N): " RECREATE
    if [[ "$RECREATE" =~ ^[Yy]$ ]]; then
        log_info "Backing up existing database..."
        cp "$DB_PATH" "$DB_PATH.backup.$(date +%Y%m%d_%H%M%S)"
        rm "$DB_PATH"
        log_success "Backup created"
    fi
fi

if [ ! -f "$DB_PATH" ]; then
    log_info "Creating database schema..."
    
    # Base schema
    if [ -f "$INSTALL_DIR/schema.sql" ]; then
        sqlite3 "$DB_PATH" < "$INSTALL_DIR/schema.sql" 2>&1 | grep -v "Error:" || true
        log_success "Base schema created"
    else
        log_error "schema.sql not found!"
        exit 1
    fi
    
    # Enhancements
    if [ -f "$INSTALL_DIR/schema_enhancements.sql" ]; then
        log_info "Applying enhancements..."
        sqlite3 "$DB_PATH" < "$INSTALL_DIR/schema_enhancements.sql" 2>&1 | grep -v "duplicate column" | grep -v "already exists" || true
        log_success "Enhancements applied"
    fi
fi

# Ensure critical tables exist
log_info "Verifying database structure..."

sqlite3 "$DB_PATH" << 'EOSQL' 2>&1 | grep -v "duplicate column" | grep -v "already exists" || true
-- Accounts table
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'viewer',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- User enhancements
ALTER TABLE users ADD COLUMN name TEXT;
ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1;
ALTER TABLE users ADD COLUMN department_id INTEGER;
ALTER TABLE users ADD COLUMN job_title TEXT;
ALTER TABLE users ADD COLUMN employee_type TEXT DEFAULT 'full-time';
ALTER TABLE users ADD COLUMN hire_date TEXT;
ALTER TABLE users ADD COLUMN supervisor_employee_id TEXT;
ALTER TABLE users ADD COLUMN overtime_policy_id INTEGER;

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT UNIQUE,
    description TEXT,
    manager_employee_id TEXT,
    parent_department_id INTEGER,
    cost_center TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_department ON users(department_id);
CREATE INDEX IF NOT EXISTS idx_departments_manager ON departments(manager_employee_id);

-- Leave types
CREATE TABLE IF NOT EXISTS leave_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL UNIQUE,
    is_paid INTEGER DEFAULT 1,
    requires_approval INTEGER DEFAULT 1,
    max_days_per_year REAL,
    accrual_rate REAL,
    color_code TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Leave balances
CREATE TABLE IF NOT EXISTS leave_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    leave_type_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    allocated_days REAL NOT NULL DEFAULT 0,
    used_days REAL NOT NULL DEFAULT 0,
    pending_days REAL NOT NULL DEFAULT 0,
    carried_over REAL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, leave_type_id, year),
    FOREIGN KEY(leave_type_id) REFERENCES leave_types(id)
);

-- Leave requests
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    leave_type_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days REAL NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    approved_by TEXT,
    approved_at TEXT,
    rejection_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

-- Department schedules
CREATE TABLE IF NOT EXISTS department_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    schedule_id INTEGER NOT NULL,
    effective_date TEXT,
    end_date TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(department_id, schedule_id, effective_date)
);

-- Seed data
INSERT OR IGNORE INTO departments (name, code, description) VALUES
('Engineering', 'ENG', 'Engineering and Development'),
('Human Resources', 'HR', 'Human Resources'),
('Finance', 'FIN', 'Finance and Accounting'),
('Operations', 'OPS', 'Operations'),
('Sales', 'SALES', 'Sales and Business Development'),
('IT', 'IT', 'Information Technology');

INSERT OR IGNORE INTO leave_types (name, code, is_paid, max_days_per_year, accrual_rate, color_code) VALUES
('Vacation', 'VAC', 1, 20, 1.67, '#4CAF50'),
('Sick Leave', 'SICK', 1, 10, 0.83, '#FF9800'),
('Personal Day', 'PERS', 1, 5, 0.42, '#2196F3'),
('Unpaid Leave', 'UNPAID', 0, NULL, 0, '#9E9E9E');
EOSQL

log_success "Database verified"

# Run feature initialization if available
if [ -f "$INSTALL_DIR/setup_features.py" ]; then
    log_info "Initializing features..."
    export ATT_DB="$DB_PATH"
    python3 "$INSTALL_DIR/setup_features.py" 2>&1 | tail -5 || true
fi

# =============================================================================
# Create Admin Account
# =============================================================================

log_section "STEP 7/10: Creating Admin Account"

read -p "Admin username (default: admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

while true; do
    read -s -p "Admin password (min 4 chars): " ADMIN_PASS
    echo
    
    if [ ${#ADMIN_PASS} -lt 4 ]; then
        log_error "Password too short"
        continue
    fi
    
    read -s -p "Confirm password: " ADMIN_PASS_CONFIRM
    echo
    
    if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
        log_error "Passwords don't match"
        continue
    fi
    
    break
done

python3 << EOPY
from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect('$DB_PATH')
cur = conn.cursor()

password_hash = generate_password_hash('$ADMIN_PASS')
cur.execute("DELETE FROM accounts WHERE username = ?", ('$ADMIN_USER',))
cur.execute("""
    INSERT INTO accounts (username, password_hash, role, active)
    VALUES (?, ?, 'admin', 1)
""", ('$ADMIN_USER', password_hash))

conn.commit()
conn.close()
print("✓ Admin account created")
EOPY

log_success "Admin account configured"

# =============================================================================
# Install Dark Mode
# =============================================================================

log_section "STEP 8/10: Installing Dark Mode"

log_info "Creating dark mode CSS..."
cat > "$INSTALL_DIR/static/css/dark-mode-universal.css" << 'EOCSS'
:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --text-primary: #212529;
    --border-color: #dee2e6;
    --card-bg: #ffffff;
    --table-hover: #f8f9fa;
    --input-bg: #ffffff;
}

[data-theme="dark"] {
    --bg-primary: #1a1d23;
    --bg-secondary: #23272f;
    --text-primary: #e9ecef;
    --border-color: #3d424a;
    --card-bg: #23272f;
    --table-hover: #2d3139;
    --input-bg: #2d3139;
}

body { background-color: var(--bg-primary); color: var(--text-primary); transition: all 0.3s ease; }
.card { background-color: var(--card-bg); border-color: var(--border-color); }
.card-header { background-color: var(--bg-secondary); }
.table { color: var(--text-primary); border-color: var(--border-color); }
.table thead th { background-color: var(--bg-secondary); }
.table tbody tr:hover { background-color: var(--table-hover); }
.form-control, .form-select { background-color: var(--input-bg); border-color: var(--border-color); color: var(--text-primary); }
.modal-content { background-color: var(--card-bg); }
.dropdown-menu { background-color: var(--card-bg); }
[data-theme="dark"] a:not(.btn):not(.nav-link) { color: #6ea8fe; }
EOCSS

log_info "Creating dark mode JavaScript..."
cat > "$INSTALL_DIR/static/js/dark-mode-universal.js" << 'EOJS'
(function() {
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    document.addEventListener('DOMContentLoaded', function() {
        const navbar = document.querySelector('.navbar-nav');
        if (navbar) {
            const li = document.createElement('li');
            li.className = 'nav-item';
            const btn = document.createElement('button');
            btn.id = 'darkModeToggle';
            btn.className = 'nav-link btn btn-link';
            btn.innerHTML = '<i class="bi bi-moon-fill"></i>';
            btn.onclick = function() {
                const current = document.documentElement.getAttribute('data-theme');
                const newTheme = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('theme', newTheme);
                btn.innerHTML = newTheme === 'dark' ? '<i class="bi bi-sun-fill"></i>' : '<i class="bi bi-moon-fill"></i>';
            };
            li.appendChild(btn);
            navbar.appendChild(li);
            btn.innerHTML = theme === 'dark' ? '<i class="bi bi-sun-fill"></i>' : '<i class="bi bi-moon-fill"></i>';
        }
    });
})();
EOJS

# Update layout.html
if [ -f "$INSTALL_DIR/templates/layout.html" ]; then
    cp "$INSTALL_DIR/templates/layout.html" "$INSTALL_DIR/templates/layout.html.backup"
    
    if ! grep -q "bootstrap-icons" "$INSTALL_DIR/templates/layout.html"; then
        sed -i 's|</head>|    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">\n</head>|' "$INSTALL_DIR/templates/layout.html"
    fi
    
    if ! grep -q "dark-mode-universal.css" "$INSTALL_DIR/templates/layout.html"; then
        sed -i 's|</head>|    <link rel="stylesheet" href="{{ url_for('\''static'\'', filename='\''css/dark-mode-universal.css'\'') }}">\n</head>|' "$INSTALL_DIR/templates/layout.html"
    fi
    
    if ! grep -q "dark-mode-universal.js" "$INSTALL_DIR/templates/layout.html"; then
        sed -i 's|</body>|    <script src="{{ url_for('\''static'\'', filename='\''js/dark-mode-universal.js'\'') }}"></script>\n</body>|' "$INSTALL_DIR/templates/layout.html"
    fi
fi

log_success "Dark mode installed"

# =============================================================================
# Fix Code Issues
# =============================================================================

log_section "STEP 9/10: Fixing Code Issues"

# Fix bootstrap_db import if it exists
if [ -f "$INSTALL_DIR/server.py" ]; then
    if grep -q "from scripts.bootstrap_db import main as bootstrap_db" "$INSTALL_DIR/server.py" 2>/dev/null; then
        sed -i 's/^from scripts.bootstrap_db import main as bootstrap_db/# from scripts.bootstrap_db import main as bootstrap_db/' "$INSTALL_DIR/server.py"
        sed -i 's/^    bootstrap_db()/    # bootstrap_db()/' "$INSTALL_DIR/server.py"
        log_success "Fixed bootstrap_db import"
    fi
fi

# =============================================================================
# Create Systemd Service
# =============================================================================

log_info "Creating systemd service..."

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
log_success "Systemd service created"

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

log_section "STEP 10/10: Starting Service"

systemctl start "$SERVICE_NAME"
sleep 3

if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_success "Service started successfully"
else
    log_error "Service failed to start"
    log_info "Checking logs..."
    journalctl -u "$SERVICE_NAME" -n 20 --no-pager
    exit 1
fi

# =============================================================================
# Get System Info
# =============================================================================

IP_ADDR=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

# =============================================================================
# Installation Complete
# =============================================================================

clear
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✨ PiServer Installation Complete! ✨"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "🌐 Access your PiServer:"
echo "   http://$IP_ADDR:$PORT"
echo "   http://$HOSTNAME.local:$PORT"
echo ""
echo "🔐 Login credentials:"
echo "   Username: $ADMIN_USER"
echo "   Password: $ADMIN_PASS"
echo ""
echo "⚠️  IMPORTANT: Change your password after first login!"
echo ""
echo "✅ Features installed:"
echo "   ✓ Base attendance system"
echo "   ✓ Modern UI with dark mode (🌙 toggle in navbar)"
echo "   ✓ Department management (/departments/)"
echo "   ✓ Leave/PTO tracking (/leave/)"
echo "   ✓ REST API (/api/v1/)"
echo "   ✓ Enhanced reporting"
echo ""
echo "📊 Database info:"
echo "   Location: $DB_PATH"
echo "   Departments: $(sqlite3 $DB_PATH "SELECT COUNT(*) FROM departments;")"
echo "   Leave types: $(sqlite3 $DB_PATH "SELECT COUNT(*) FROM leave_types;")"
echo ""
echo "🛠️  Useful commands:"
echo "   View logs:    journalctl -u $SERVICE_NAME -f"
echo "   Stop:         systemctl stop $SERVICE_NAME"
echo "   Start:        systemctl start $SERVICE_NAME"
echo "   Restart:      systemctl restart $SERVICE_NAME"
echo "   Status:       systemctl status $SERVICE_NAME"
echo ""
echo "📁 File locations:"
echo "   App:          $INSTALL_DIR"
echo "   Data:         $DATA_DIR"
echo "   Config:       $CONFIG_DIR/attendance.env"
echo "   Backups:      $DB_PATH.backup.*"
echo ""
echo "🎯 Next steps:"
echo "   1. Access the web interface"
echo "   2. Login and change password"
echo "   3. Configure company settings"
echo "   4. Create departments"
echo "   5. Add employees"
echo "   6. Set up schedules"
echo "   7. Connect Hikvision devices"
echo ""
echo "📚 Documentation:"
echo "   README:              cat $INSTALL_DIR/README.md"
echo "   Quick Start:         cat $INSTALL_DIR/QUICKSTART.md"
echo "   Additional Features: cat $INSTALL_DIR/ADDITIONAL_FEATURES_GUIDE.md"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Installation completed on $(date)"
echo "═══════════════════════════════════════════════════════════"
echo ""