#!/usr/bin/env python3
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# Ensure ATT_DB exists for cron/manual runs
if not os.environ.get("ATT_DB"):
    _load_env_file(BASE_DIR / ".env")
    _load_env_file(BASE_DIR / ".env.dev")


from services.users import find_new_users_from_events, create_users
from services.devices import get_primary_fdlib_device
from collector import bulk_import_fdlib_faces
from db import get_conn

print("[SYNC] Starting daily user sync")

# --------------------------------------------------
# Step 1: Detect + create new users
# --------------------------------------------------
new_users = find_new_users_from_events()
created = 0

if new_users:
    print(f"[SYNC] Found {len(new_users)} new users from events")
    created = create_users(new_users)
    print(f"[SYNC] Created {created} users")
else:
    print("[SYNC] No new users detected")

# --------------------------------------------------
# Step 2: Only import faces if users were created
# --------------------------------------------------
if created == 0:
    print("[SYNC] No new users created — skipping FDLib face import")
    print("[SYNC] Done")
    sys.exit(0)

device = get_primary_fdlib_device()
if not device:
    print("[SYNC] No FDLib-enabled device found — skipping face import")
    print("[SYNC] Done")
    sys.exit(0)

if not device.get("ip") or not device.get("username") or not device.get("password"):
    print(f"[SYNC] FDLib device '{device.get('name')}' missing credentials — skipping face import")
    print("[SYNC] Done")
    sys.exit(0)

print(f"[SYNC] Importing faces from FDLib device '{device['name']}' ({device['ip']})")

try:
    result = bulk_import_fdlib_faces(
        device["ip"],
        device["username"],
        device["password"]
    )
    print(
        f"[SYNC] FDLib import complete "
        f"(Imported: {result.get('imported')}, Skipped: {result.get('skipped')})"
    )
except Exception as e:
    print(f"[SYNC] ERROR importing from '{device['name']}': {e}")
    print("[SYNC] Done")
    sys.exit(1)

# --------------------------------------------------
# Step 3: Sanity check — faces exist for new users
# --------------------------------------------------
conn = get_conn()
missing_faces = conn.execute(
    """
    SELECT u.employee_id
    FROM users u
    LEFT JOIN user_faces f ON f.employee_id = u.employee_id
    WHERE f.employee_id IS NULL
    """
).fetchall()
conn.close()

if missing_faces:
    print(f"[SYNC][WARN] {len(missing_faces)} users still missing faces after FDLib import")

print("[SYNC] Done")
