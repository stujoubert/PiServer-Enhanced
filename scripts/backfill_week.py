#!/usr/bin/env python3
import os
import sys

# -------------------------------------------------
# Ensure project root is on PYTHONPATH
# -------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import argparse
import sqlite3
import subprocess
from datetime import datetime, timedelta


def log(msg):
    print(f"[BACKFILL] {msg}", flush=True)


def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date()


def get_db_path():
    return os.environ.get("ATT_DB") or "/opt/attendance/attendance.db"


def table_exists(db, name):
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def purge_day(db, day_iso):
    if table_exists(db, "events"):
        db.execute(
            "DELETE FROM events WHERE DATE(event_time) = ?",
            (day_iso,),
        )

    if table_exists(db, "payroll_cache"):
        db.execute(
            "DELETE FROM payroll_cache WHERE work_date = ?",
            (day_iso,),
        )

    if table_exists(db, "daily_attendance"):
        db.execute(
            "DELETE FROM daily_attendance WHERE work_date = ?",
            (day_iso,),
        )

    db.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", help="YYYY-MM-DD")
    parser.add_argument("--end", help="YYYY-MM-DD")
    args = parser.parse_args()

    today = datetime.now().date()
    if args.start and args.end:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end)
    else:
        end_date = today
        start_date = end_date - timedelta(days=7)

    log(f"Backfilling from {start_date} to {end_date}")

    db = sqlite3.connect(get_db_path())
    db.row_factory = sqlite3.Row

    current = start_date
    while current <= end_date:
        day_iso = current.isoformat()
        log(f"Rebuilding {day_iso}")

        # 1. Remove derived data for the day
        purge_day(db, day_iso)

        # 2. Re-run canonical sync
        subprocess.check_call([
            "python3",
            "/opt/attendance/scripts/daily_sync.py",
            "--date",
            day_iso
        ])

        current += timedelta(days=1)

    log("Backfill completed successfully")


if __name__ == "__main__":
    main()
