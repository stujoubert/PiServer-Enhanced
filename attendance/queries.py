from datetime import datetime
from collections import defaultdict


def fetch_raw_events(conn, start_date, end_date):
    """
    Fetch raw events grouped by employee and date.
    Normalizes DB schema (timestamp -> event_time).
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            employee_id,
            device_id,
            timestamp,
            direction
        FROM events
        WHERE DATE(timestamp) BETWEEN ? AND ?
          AND employee_id IS NOT NULL
        ORDER BY employee_id, timestamp
        """,
        (start_date, end_date),
    )

    grouped = defaultdict(lambda: defaultdict(list))

    for employee_id, device_id, ts, direction in cur.fetchall():
        dt = datetime.fromisoformat(ts)

        grouped[str(employee_id)][dt.date()].append({
            "employee_id": str(employee_id),
            "device_id": device_id,
            "event_time": dt,          # 🔒 normalized name
            "direction": direction,
        })

    return grouped
