#!/bin/bash
# =============================================================================
# PiServer - Complete Department System Installer
# Installs departments, department-schedule integration, and UI
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

if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════"
echo "  PiServer - Department System Installer"
echo "═══════════════════════════════════════════════════════════"
echo ""

INSTALL_DIR="${1:-/opt/attendance}"
DB_PATH="${ATT_DB:-/var/lib/attendance/attendance.db}"

if [ ! -d "$INSTALL_DIR" ]; then
    log_error "Installation directory not found: $INSTALL_DIR"
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    log_error "Database not found: $DB_PATH"
    exit 1
fi

log_info "Installing to: $INSTALL_DIR"
log_info "Database: $DB_PATH"

# =============================================================================
# Backup Database
# =============================================================================

log_info "Creating database backup..."
cp "$DB_PATH" "$DB_PATH.backup.$(date +%Y%m%d_%H%M%S)"
log_success "Backup created"

# =============================================================================
# Create Department Tables
# =============================================================================

log_info "Creating department tables..."

sqlite3 "$DB_PATH" << 'EOSQL' 2>&1 | grep -v "duplicate column" | grep -v "already exists" || true
-- Departments table
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
    updated_at TEXT,
    FOREIGN KEY(parent_department_id) REFERENCES departments(id)
);

-- Add department fields to users table
ALTER TABLE users ADD COLUMN department_id INTEGER REFERENCES departments(id);
ALTER TABLE users ADD COLUMN job_title TEXT;
ALTER TABLE users ADD COLUMN employee_type TEXT DEFAULT 'full-time';
ALTER TABLE users ADD COLUMN hire_date TEXT;
ALTER TABLE users ADD COLUMN supervisor_employee_id TEXT;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_department ON users(department_id);
CREATE INDEX IF NOT EXISTS idx_departments_manager ON departments(manager_employee_id);

-- Department-Schedule integration
ALTER TABLE schedules ADD COLUMN department_id INTEGER REFERENCES departments(id);
CREATE INDEX IF NOT EXISTS idx_schedules_department ON schedules(department_id);

CREATE TABLE IF NOT EXISTS department_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    schedule_id INTEGER NOT NULL,
    effective_date TEXT,
    end_date TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(department_id) REFERENCES departments(id) ON DELETE CASCADE,
    FOREIGN KEY(schedule_id) REFERENCES schedules(id) ON DELETE CASCADE,
    UNIQUE(department_id, schedule_id, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_dept_schedules_dept ON department_schedules(department_id);
CREATE INDEX IF NOT EXISTS idx_dept_schedules_schedule ON department_schedules(schedule_id);

-- View for department schedules
CREATE VIEW IF NOT EXISTS v_department_schedules AS
SELECT 
    d.id AS department_id,
    d.name AS department_name,
    d.code AS department_code,
    s.id AS schedule_id,
    s.name AS schedule_name,
    ds.effective_date,
    ds.end_date,
    ds.is_active,
    COUNT(DISTINCT u.employee_id) AS employee_count
FROM departments d
LEFT JOIN department_schedules ds ON ds.department_id = d.id
LEFT JOIN schedules s ON s.id = ds.schedule_id
LEFT JOIN users u ON u.department_id = d.id AND u.is_active = 1
WHERE d.is_active = 1
GROUP BY d.id, s.id, ds.id;

-- Insert default departments
INSERT OR IGNORE INTO departments (name, code, description) VALUES
('Engineering', 'ENG', 'Engineering and Development'),
('Human Resources', 'HR', 'Human Resources'),
('Finance', 'FIN', 'Finance and Accounting'),
('Operations', 'OPS', 'Operations and Logistics'),
('Sales', 'SALES', 'Sales and Business Development'),
('Marketing', 'MKT', 'Marketing and Communications'),
('IT', 'IT', 'Information Technology'),
('Customer Support', 'CS', 'Customer Support and Service');
EOSQL

log_success "Database tables created"

# =============================================================================
# Verify Tables
# =============================================================================

log_info "Verifying installation..."

DEPT_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM departments;")
log_success "Departments table has $DEPT_COUNT records"

# =============================================================================
# Check for Routes Files
# =============================================================================

log_info "Checking for department route files..."

ROUTES_NEEDED=()

if [ ! -f "$INSTALL_DIR/routes/departments.py" ]; then
    ROUTES_NEEDED+=("departments.py")
    log_warning "routes/departments.py not found"
fi

if [ ! -f "$INSTALL_DIR/routes/department_schedules.py" ]; then
    ROUTES_NEEDED+=("department_schedules.py")
    log_warning "routes/department_schedules.py not found"
fi

if [ ${#ROUTES_NEEDED[@]} -gt 0 ]; then
    log_warning "Missing route files: ${ROUTES_NEEDED[*]}"
    log_info "Please copy these files from the complete package"
    log_info "Or download from GitHub"
else
    log_success "All route files present"
fi

# =============================================================================
# Register Routes in server.py
# =============================================================================

log_info "Checking route registration in server.py..."

ROUTES_TO_ADD=()

if ! grep -q "routes.departments" "$INSTALL_DIR/server.py"; then
    ROUTES_TO_ADD+=("departments")
fi

if ! grep -q "routes.department_schedules" "$INSTALL_DIR/server.py"; then
    ROUTES_TO_ADD+=("department_schedules")
fi

if [ ${#ROUTES_TO_ADD[@]} -gt 0 ]; then
    log_info "Routes need to be registered: ${ROUTES_TO_ADD[*]}"
    
    read -p "Auto-register routes in server.py? (y/N): " AUTO_REGISTER
    
    if [[ "$AUTO_REGISTER" =~ ^[Yy]$ ]]; then
        # Backup server.py
        cp "$INSTALL_DIR/server.py" "$INSTALL_DIR/server.py.backup.$(date +%Y%m%d_%H%M%S)"
        
        for route in "${ROUTES_TO_ADD[@]}"; do
            if [ "$route" == "departments" ] && [ -f "$INSTALL_DIR/routes/departments.py" ]; then
                log_info "Registering routes.departments..."
                sed -i '/from routes.dashboard import bp as dashboard_bp/a from routes.departments import bp as departments_bp' "$INSTALL_DIR/server.py"
                sed -i '/register(dashboard_bp, "routes.dashboard")/a register(departments_bp, "routes.departments")' "$INSTALL_DIR/server.py"
                log_success "departments route registered"
            fi
            
            if [ "$route" == "department_schedules" ] && [ -f "$INSTALL_DIR/routes/department_schedules.py" ]; then
                log_info "Registering routes.department_schedules..."
                sed -i '/from routes.departments import bp as departments_bp/a from routes.department_schedules import bp as department_schedules_bp' "$INSTALL_DIR/server.py"
                sed -i '/register(departments_bp, "routes.departments")/a register(department_schedules_bp, "routes.department_schedules")' "$INSTALL_DIR/server.py"
                log_success "department_schedules route registered"
            fi
        done
    else
        log_info "Manual registration required. Add to server.py:"
        echo ""
        echo "  from routes.departments import bp as departments_bp"
        echo "  register(departments_bp, \"routes.departments\")"
        echo ""
        echo "  from routes.department_schedules import bp as department_schedules_bp"
        echo "  register(department_schedules_bp, \"routes.department_schedules\")"
        echo ""
    fi
else
    log_success "All routes already registered"
fi

# =============================================================================
# Restart Service
# =============================================================================

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
else
    log_warning "Service not running"
fi

# =============================================================================
# Installation Complete
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Department System Installation Complete! 🎉"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Database changes:"
echo "  ✓ departments table created"
echo "  ✓ department_schedules table created"
echo "  ✓ Users table enhanced with department fields"
echo "  ✓ $DEPT_COUNT default departments added"
echo ""
echo "Access department management:"
echo "  http://$(hostname -I | awk '{print $1}'):5000/departments/"
echo ""
echo "Features available:"
echo "  ✓ Create/edit departments"
echo "  ✓ Assign employees to departments"
echo "  ✓ Set department managers"
echo "  ✓ View department hierarchy"
echo "  ✓ Assign schedules to departments"
echo "  ✓ Department analytics"
echo ""
echo "Next steps:"
echo "  1. Login to your PiServer"
echo "  2. Navigate to 'Departments' in the menu"
echo "  3. Review/edit default departments"
echo "  4. Start assigning employees to departments"
echo "  5. Assign schedules to departments"
echo ""

if [ ${#ROUTES_NEEDED[@]} -gt 0 ]; then
    echo "⚠ IMPORTANT: Missing route files"
    echo "  Please copy: ${ROUTES_NEEDED[*]}"
    echo "  From: ~/piserver-complete/routes/"
    echo "  To: $INSTALL_DIR/routes/"
    echo ""
fi

echo "═══════════════════════════════════════════════════════════"
