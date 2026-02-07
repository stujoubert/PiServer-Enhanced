-- =============================================================================
-- Additional Schema Enhancements for PiServer
-- =============================================================================
-- Run this after your existing schema.sql
-- These additions add: departments, leave management, overtime policies, and more
-- =============================================================================

-- -----------------------------------------------------------------------------
-- DEPARTMENTS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT UNIQUE,                      -- Short code (e.g., "ENG", "HR")
    description TEXT,
    manager_employee_id TEXT,              -- Department manager
    parent_department_id INTEGER,          -- For nested departments
    cost_center TEXT,                      -- For accounting
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY(parent_department_id) REFERENCES departments(id)
);

-- Add department to users table
ALTER TABLE users ADD COLUMN department_id INTEGER REFERENCES departments(id);
ALTER TABLE users ADD COLUMN job_title TEXT;
ALTER TABLE users ADD COLUMN employee_type TEXT DEFAULT 'full-time' 
    CHECK(employee_type IN ('full-time', 'part-time', 'contractor', 'intern'));
ALTER TABLE users ADD COLUMN hire_date TEXT;
ALTER TABLE users ADD COLUMN supervisor_employee_id TEXT;  -- Direct supervisor

CREATE INDEX idx_users_department ON users(department_id);
CREATE INDEX idx_departments_manager ON departments(manager_employee_id);

-- -----------------------------------------------------------------------------
-- LEAVE / PTO MANAGEMENT
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS leave_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,              -- "Vacation", "Sick", "Personal"
    code TEXT NOT NULL UNIQUE,              -- "VAC", "SICK", "PERS"
    is_paid INTEGER DEFAULT 1,
    requires_approval INTEGER DEFAULT 1,
    max_days_per_year REAL,                -- NULL = unlimited
    accrual_rate REAL,                      -- Days per month
    color_code TEXT,                        -- For calendar display
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    leave_type_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    allocated_days REAL NOT NULL DEFAULT 0,
    used_days REAL NOT NULL DEFAULT 0,
    pending_days REAL NOT NULL DEFAULT 0,   -- Awaiting approval
    carried_over REAL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, leave_type_id, year),
    FOREIGN KEY(leave_type_id) REFERENCES leave_types(id)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    leave_type_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days REAL NOT NULL,                    -- Including partial days
    reason TEXT,
    status TEXT DEFAULT 'pending' 
        CHECK(status IN ('pending', 'approved', 'rejected', 'cancelled')),
    approved_by TEXT,                       -- employee_id of approver
    approved_at TEXT,
    rejection_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY(leave_type_id) REFERENCES leave_types(id)
);

CREATE INDEX idx_leave_requests_employee ON leave_requests(employee_id);
CREATE INDEX idx_leave_requests_dates ON leave_requests(start_date, end_date);
CREATE INDEX idx_leave_requests_status ON leave_requests(status);

-- -----------------------------------------------------------------------------
-- OVERTIME POLICIES
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS overtime_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    daily_threshold_hours REAL DEFAULT 8,     -- OT after 8 hours/day
    weekly_threshold_hours REAL DEFAULT 40,   -- OT after 40 hours/week
    daily_multiplier REAL DEFAULT 1.5,        -- 1.5x for daily OT
    weekly_multiplier REAL DEFAULT 1.5,       -- 1.5x for weekly OT
    weekend_multiplier REAL DEFAULT 2.0,      -- 2x for weekends
    holiday_multiplier REAL DEFAULT 2.5,      -- 2.5x for holidays
    auto_approve_under_hours REAL,            -- Auto-approve OT under X hours
    requires_approval INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Assign policy to employees
ALTER TABLE users ADD COLUMN overtime_policy_id INTEGER 
    REFERENCES overtime_policies(id);

CREATE TABLE IF NOT EXISTS overtime_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    date TEXT NOT NULL,
    hours REAL NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending' 
        CHECK(status IN ('pending', 'approved', 'rejected', 'auto-approved')),
    approved_by TEXT,
    approved_at TEXT,
    rejection_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_overtime_requests_employee ON overtime_requests(employee_id);

-- -----------------------------------------------------------------------------
-- WORK HOURS TRACKING (Enhanced)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS daily_hours_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    date TEXT NOT NULL,
    scheduled_hours REAL,
    actual_hours REAL,
    regular_hours REAL,
    overtime_hours REAL,
    break_hours REAL,
    late_minutes INTEGER DEFAULT 0,
    early_leave_minutes INTEGER DEFAULT 0,
    status TEXT CHECK(status IN ('present', 'absent', 'leave', 'holiday', 'weekend')),
    notes TEXT,
    approved INTEGER DEFAULT 0,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, date)
);

CREATE INDEX idx_daily_hours_employee ON daily_hours_summary(employee_id);
CREATE INDEX idx_daily_hours_date ON daily_hours_summary(date);

-- -----------------------------------------------------------------------------
-- HOLIDAYS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    type TEXT CHECK(type IN ('public', 'company', 'optional')),
    recurring INTEGER DEFAULT 0,            -- 1 = repeats annually
    applies_to_departments TEXT,            -- Comma-separated dept IDs or NULL for all
    is_paid INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, date)
);

CREATE INDEX idx_holidays_date ON holidays(date);

-- -----------------------------------------------------------------------------
-- SHIFT SWAPS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS shift_swaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_employee_id TEXT NOT NULL,
    target_employee_id TEXT NOT NULL,
    original_date TEXT NOT NULL,
    swap_date TEXT NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending' 
        CHECK(status IN ('pending', 'accepted', 'rejected', 'approved', 'cancelled')),
    target_accepted_at TEXT,
    manager_approved_by TEXT,
    manager_approved_at TEXT,
    rejection_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shift_swaps_requester ON shift_swaps(requester_employee_id);
CREATE INDEX idx_shift_swaps_target ON shift_swaps(target_employee_id);

-- -----------------------------------------------------------------------------
-- NOTIFICATIONS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,              -- Recipient
    type TEXT NOT NULL,                     -- 'leave_request', 'overtime', 'shift_swap', etc.
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_id INTEGER,                     -- ID of related record
    is_read INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'normal' CHECK(priority IN ('low', 'normal', 'high', 'urgent')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    read_at TEXT
);

CREATE INDEX idx_notifications_employee ON notifications(employee_id);
CREATE INDEX idx_notifications_read ON notifications(is_read);

-- -----------------------------------------------------------------------------
-- AUDIT LOG
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_employee_id TEXT,                 -- Who made the change
    action TEXT NOT NULL,                   -- 'create', 'update', 'delete', 'approve'
    table_name TEXT NOT NULL,
    record_id INTEGER,
    changes TEXT,                           -- JSON of old vs new values
    ip_address TEXT,
    user_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_actor ON audit_log(actor_employee_id);
CREATE INDEX idx_audit_log_table ON audit_log(table_name);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);

-- -----------------------------------------------------------------------------
-- EMPLOYEE DOCUMENTS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS employee_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    document_type TEXT NOT NULL,            -- 'contract', 'id', 'certificate', etc.
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    uploaded_by TEXT,
    expiry_date TEXT,                       -- For documents that expire
    is_verified INTEGER DEFAULT 0,
    verified_by TEXT,
    verified_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_employee_documents_employee ON employee_documents(employee_id);
CREATE INDEX idx_employee_documents_expiry ON employee_documents(expiry_date);

-- -----------------------------------------------------------------------------
-- PAYROLL ADJUSTMENTS
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS payroll_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    pay_period_start TEXT NOT NULL,
    pay_period_end TEXT NOT NULL,
    adjustment_type TEXT NOT NULL,          -- 'bonus', 'deduction', 'allowance', 'reimbursement'
    amount REAL NOT NULL,
    reason TEXT,
    approved_by TEXT,
    approved_at TEXT,
    processed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payroll_adjustments_employee ON payroll_adjustments(employee_id);

-- -----------------------------------------------------------------------------
-- SEED DATA - Insert Default Values
-- -----------------------------------------------------------------------------

-- Default Leave Types
INSERT OR IGNORE INTO leave_types (name, code, is_paid, requires_approval, max_days_per_year, accrual_rate, color_code) VALUES
('Vacation', 'VAC', 1, 1, 20, 1.67, '#4CAF50'),
('Sick Leave', 'SICK', 1, 0, 10, 0.83, '#FF9800'),
('Personal Day', 'PERS', 1, 1, 5, 0.42, '#2196F3'),
('Unpaid Leave', 'UNPAID', 0, 1, NULL, 0, '#9E9E9E'),
('Bereavement', 'BERV', 1, 0, 5, 0, '#607D8B'),
('Maternity', 'MAT', 1, 1, 90, 0, '#E91E63'),
('Paternity', 'PAT', 1, 1, 14, 0, '#3F51B5');

-- Default Overtime Policy
INSERT OR IGNORE INTO overtime_policies (name, daily_threshold_hours, weekly_threshold_hours, daily_multiplier, weekly_multiplier, weekend_multiplier, holiday_multiplier, auto_approve_under_hours, requires_approval) VALUES
('Standard Policy', 8, 40, 1.5, 1.5, 2.0, 2.5, 2, 1);

-- Default Departments
INSERT OR IGNORE INTO departments (name, code, description) VALUES
('Engineering', 'ENG', 'Engineering and Development'),
('Human Resources', 'HR', 'Human Resources'),
('Finance', 'FIN', 'Finance and Accounting'),
('Operations', 'OPS', 'Operations'),
('Sales', 'SALES', 'Sales and Business Development'),
('Marketing', 'MKT', 'Marketing'),
('IT', 'IT', 'Information Technology'),
('Customer Support', 'CS', 'Customer Support');

-- Default Holidays (US-based, modify as needed)
INSERT OR IGNORE INTO holidays (name, date, type, recurring, is_paid) VALUES
('New Year''s Day', '2026-01-01', 'public', 1, 1),
('Independence Day', '2026-07-04', 'public', 1, 1),
('Labor Day', '2026-09-07', 'public', 1, 1),
('Thanksgiving', '2026-11-26', 'public', 1, 1),
('Christmas Day', '2026-12-25', 'public', 1, 1);

-- -----------------------------------------------------------------------------
-- VIEWS FOR REPORTING
-- -----------------------------------------------------------------------------

-- Current Leave Balances View
CREATE VIEW IF NOT EXISTS v_current_leave_balances AS
SELECT 
    lb.employee_id,
    u.name AS employee_name,
    lt.name AS leave_type,
    lt.code AS leave_code,
    lb.year,
    lb.allocated_days,
    lb.used_days,
    lb.pending_days,
    (lb.allocated_days - lb.used_days - lb.pending_days) AS available_days
FROM leave_balances lb
JOIN users u ON u.employee_id = lb.employee_id
JOIN leave_types lt ON lt.id = lb.leave_type_id
WHERE lb.year = strftime('%Y', 'now');

-- Department Summary View
CREATE VIEW IF NOT EXISTS v_department_summary AS
SELECT 
    d.id,
    d.name,
    d.code,
    COUNT(u.id) AS employee_count,
    COUNT(CASE WHEN u.is_active = 1 THEN 1 END) AS active_employees,
    d.manager_employee_id,
    m.name AS manager_name
FROM departments d
LEFT JOIN users u ON u.department_id = d.id
LEFT JOIN users m ON m.employee_id = d.manager_employee_id
WHERE d.is_active = 1
GROUP BY d.id;

-- Pending Approvals View
CREATE VIEW IF NOT EXISTS v_pending_approvals AS
SELECT 
    'leave' AS type,
    lr.id,
    lr.employee_id,
    u.name AS employee_name,
    lt.name AS leave_type,
    lr.start_date,
    lr.end_date,
    lr.days,
    lr.created_at
FROM leave_requests lr
JOIN users u ON u.employee_id = lr.employee_id
JOIN leave_types lt ON lt.id = lr.leave_type_id
WHERE lr.status = 'pending'
UNION ALL
SELECT 
    'overtime' AS type,
    ot.id,
    ot.employee_id,
    u.name AS employee_name,
    'Overtime' AS leave_type,
    ot.date AS start_date,
    ot.date AS end_date,
    ot.hours AS days,
    ot.created_at
FROM overtime_requests ot
JOIN users u ON u.employee_id = ot.employee_id
WHERE ot.status = 'pending'
ORDER BY created_at DESC;

-- =============================================================================
-- MIGRATION NOTES
-- =============================================================================
-- After running this schema:
-- 1. Update existing users with departments
-- 2. Initialize leave balances for current year
-- 3. Assign overtime policies to employees
-- 4. Import company holidays
-- =============================================================================
