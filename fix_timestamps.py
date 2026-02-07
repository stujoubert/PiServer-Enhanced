# fix_timestamps.py
import sqlite3
from datetime import datetime

DB_PATH = "/var/lib/attendance/attendance.db"

def normalize(ts):
    if ts is None:
        return None

    # strip timezone
    for sep in ["+", "-"]:
        if sep in ts[11:]:
            ts = ts.rsplit(sep, 1)[0]
            break

    ts = ts.replace("T", " ")

    try:
        dt = datetime.fromisoformat(ts)
    except:
        if "." in ts:
            ts = ts.split(".")[0]
            dt = datetime.fromisoformat(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT id, timestamp FROM events")
rows = cur.fetchall()

for event_id, ts in rows:
    new_ts = normalize(ts)
    cur.execute("UPDATE events SET timestamp=? WHERE id=?", (new_ts, event_id))

conn.commit()
conn.close()
print("DONE! All timestamps normalized.")
