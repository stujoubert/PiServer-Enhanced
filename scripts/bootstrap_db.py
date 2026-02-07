from pathlib import Path
import sqlite3
import sys
import os

db_path = os.environ.get("ATT_DB")
if not db_path:
    print("ERROR: ATT_DB not set")
    sys.exit(1)

db_file = Path(db_path)
db_file.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_file)
cur = conn.cursor()

# ---- schema ----
cur.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT UNIQUE,
    name TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT,
    timestamp TEXT,
    confidence REAL,
    image_path TEXT
);

CREATE TABLE IF NOT EXISTS user_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT,
    picture_url TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
""")

conn.commit()
conn.close()

print(f"[OK] Database ready at {db_file}")
