#!/usr/bin/env python3
import sys
from datetime import datetime, timedelta

from collector import fetch_from_device
from db import get_conn

# --------------------------------------------------
# Validate CLI arguments
# --------------------------------------------------
if len(sys.argv) != 2:
    print("Usage: backfill_day.py YYYY-MM-DD")
    sys.exit(1)

try:
    target_day = datetime.fromisoformat(sys.argv[1]).date()
except Exception:
    print("Invalid date format. Use YYYY-MM-DD")
    sys.exit(1)

print(f"Backfilling {target_day.isoformat()}")

# --------------------------------------------------
# Build EXACT time window (matches Postman)
# 01:00:00 → 23:59:59 local time
# --------------------------------------------------
start_dt = datetime.combine(target_day, datetime.min.time()) + timedelta(hours=1)
end_dt   = datetime.combine(target_day, datetime.max.time())

start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-06:00")
end_iso   = end_dt.strftime("%Y-%m-%dT%H:%M:%S-06:00")

# --------------------------------------------------
# Fetch for ALL devices
# --------------------------------------------------
conn = get_conn()
devices = conn.execute(
    "SELECT id, ip, username, password FROM devices"
).fetchall()
conn.close()

for d in devices:
    fetch_from_device(
        ip=d["ip"],
        username=d["username"],
        password=d["password"],
        start=start_iso,
        end=end_iso,
        device_id=d["id"],
    )

print("Done")
