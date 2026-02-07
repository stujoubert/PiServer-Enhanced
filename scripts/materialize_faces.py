#!/usr/bin/env python3
import os
import sqlite3
import requests

DB_PATH = "/var/lib/attendance_dev/attendance.db"
PROJECT_ROOT = "/opt/attendance"
FACE_DIR = os.path.join(PROJECT_ROOT, "fdlib", "faces")

os.makedirs(FACE_DIR, exist_ok=True)

def log(msg):
    print(msg)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("""
    SELECT employee_id, picture_url
    FROM user_faces
    WHERE picture_url LIKE 'http%'
""").fetchall()

if not rows:
    log("No remote faces found. Nothing to do.")
    conn.close()
    exit(0)

for r in rows:
    emp_id = str(r["employee_id"]).strip()
    url = r["picture_url"]

    if not emp_id or not url:
        continue

    dst = os.path.join(FACE_DIR, f"{emp_id}.jpg")

    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        log(f"[SKIP] {emp_id} already exists")
        continue

    log(f"[FETCH] {emp_id} <- {url}")

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            log(f"  [FAIL] HTTP {resp.status_code}")
            continue

        with open(dst, "wb") as f:
            f.write(resp.content)

        rel_path = f"fdlib/faces/{emp_id}.jpg"
        cur.execute(
            "UPDATE user_faces SET picture_url = ? WHERE employee_id = ?",
            (rel_path, emp_id),
        )

        log(f"  [OK] saved {dst}")

    except Exception as e:
        log(f"  [ERROR] {e}")

conn.commit()
conn.close()

log("Done.")
