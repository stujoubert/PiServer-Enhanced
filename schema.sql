CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            ip TEXT NOT NULL,
            username TEXT,
            password TEXT,
            active INTEGER DEFAULT 1
        , last_fetch_at TEXT, last_fetch_count INTEGER);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE raw_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            employee_id TEXT,
            name TEXT,
            timestamp TEXT,
            raw TEXT
        , picture_url TEXT, serial_no INTEGER);
CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT
        , picture_url TEXT DEFAULT NULL, employee_id TEXT, card_number TEXT, pin_code TEXT, photo_path TEXT, face_image BLOB, face_source TEXT, face_updated_at TEXT, is_active INTEGER DEFAULT 1, schedule_template_id INTEGER);
CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
CREATE TABLE device_users (
            device_id   INTEGER NOT NULL,
            employee_id TEXT   NOT NULL,
            name        TEXT, photo_base64 TEXT,
            PRIMARY KEY (device_id, employee_id)
        );
CREATE TABLE shift_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_time TEXT NOT NULL,          -- "HH:MM"
            end_time   TEXT NOT NULL,          -- "HH:MM"
            break_minutes INTEGER NOT NULL DEFAULT 0,
            overnight   INTEGER NOT NULL DEFAULT 0  -- 0 = no, 1 = yes
        );
CREATE TABLE shift_rotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pattern_type TEXT NOT NULL,       -- "weekly" or "cycle"
            pattern_json TEXT NOT NULL        -- JSON describing pattern
        );
CREATE TABLE employee_shift_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            rotation_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,         -- "YYYY-MM-DD"
            end_date   TEXT,                  -- NULL = open ended
            FOREIGN KEY(rotation_id) REFERENCES shift_rotations(id)
        );
CREATE TABLE employee_shift_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id  TEXT NOT NULL,
            date         TEXT NOT NULL,       -- "YYYY-MM-DD"
            shift_type_id INTEGER,            -- NULL = day off
            note         TEXT,
            FOREIGN KEY(shift_type_id) REFERENCES shift_types(id)
        );
CREATE UNIQUE INDEX idx_raw_unique
ON raw_events(device_id, serial_no);
CREATE TABLE user_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,

    weekday INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    daily_hours REAL NOT NULL,

    auto_heal INTEGER DEFAULT 1,
    allow_overtime INTEGER DEFAULT 0,

    grace_in_minutes INTEGER DEFAULT 10,
    grace_out_minutes INTEGER DEFAULT 10,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(employee_id, weekday)
);
CREATE TABLE schedule_template_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    weekday INTEGER NOT NULL,        -- 0 = Monday … 6 = Sunday

    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    daily_hours REAL NOT NULL,

    auto_heal INTEGER DEFAULT 1,
    allow_overtime INTEGER DEFAULT 0,
    grace_in_minutes INTEGER DEFAULT 10,
    grace_out_minutes INTEGER DEFAULT 10,

    UNIQUE(template_id, weekday),
    FOREIGN KEY(template_id) REFERENCES schedule_templates(id) ON DELETE CASCADE
);
CREATE TABLE schedule_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    daily_hours REAL NOT NULL,
    auto_heal INTEGER DEFAULT 1,
    allow_overtime INTEGER DEFAULT 0,
    grace_in_minutes INTEGER DEFAULT 0,
    grace_out_minutes INTEGER DEFAULT 0,
    is_workday INTEGER DEFAULT 1
, is_off_day INTEGER DEFAULT 0);
CREATE TABLE user_schedule_assignments (
  employee_id TEXT PRIMARY KEY,
  schedule_id INTEGER NOT NULL,
  assigned_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE events_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    employee_id TEXT,
    name TEXT,
    timestamp TEXT,
    type TEXT,
    picture_url TEXT,
    direction TEXT
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    employee_id TEXT,
    name TEXT,
    timestamp TEXT,
    direction TEXT,
    picture_url TEXT
, promoted INTEGER DEFAULT 0);
CREATE UNIQUE INDEX ux_events_unique
ON events (
    device_id,
    employee_id,
    timestamp,
    direction
);
CREATE VIEW v_event_audit AS
SELECT
    device_id,
    employee_id,
    name,
    timestamp,
    direction
FROM events
/* v_event_audit(device_id,employee_id,name,timestamp,direction) */;
CREATE INDEX idx_events_promoted ON events(promoted);
CREATE TABLE user_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    picture_url TEXT NOT NULL,
    source_event_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_id, picture_url)
);
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','manager','viewer')),
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_accounts_username ON accounts(username);
CREATE TABLE schedule_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    weekdays TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    FOREIGN KEY (template_id) REFERENCES schedule_templates(id)
);
CREATE TABLE schedule_shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    grace_minutes INTEGER DEFAULT 0,
    break_minutes INTEGER DEFAULT 0,
    FOREIGN KEY (rule_id) REFERENCES schedule_rules(id)
);
CREATE TABLE user_schedule_templates (
    employee_id TEXT PRIMARY KEY,
    template_id INTEGER NOT NULL,
    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES schedule_templates(id)
);
