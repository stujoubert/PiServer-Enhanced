-- =============================================================================
-- Department-Schedule Integration
-- Allows schedules to be assigned to entire departments
-- =============================================================================

-- Add department_id to schedules table
ALTER TABLE schedules ADD COLUMN department_id INTEGER REFERENCES departments(id);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_schedules_department ON schedules(department_id);

-- Create junction table for flexible many-to-many relationship
-- (A schedule can apply to multiple departments, a department can have multiple schedules)
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

-- View for easy querying of department schedules with employee counts
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

-- Example: Assign a schedule to a department
-- INSERT INTO department_schedules (department_id, schedule_id, effective_date)
-- VALUES (1, 5, '2026-02-01');

-- Example: Get all employees in departments with a specific schedule
-- SELECT u.employee_id, u.name, d.name as department, s.name as schedule
-- FROM users u
-- JOIN departments d ON u.department_id = d.id
-- JOIN department_schedules ds ON ds.department_id = d.id AND ds.is_active = 1
-- JOIN schedules s ON s.id = ds.schedule_id
-- WHERE u.is_active = 1;
