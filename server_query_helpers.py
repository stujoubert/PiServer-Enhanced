# server_query_helpers.py
from db import get_conn

def query_events_consistent(start_iso, end_iso, user_id=None, device_id=None):
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT e.id, e.device_id, e.employee_id, e.name,
               e.timestamp, e.type, d.name
        FROM events e
        LEFT JOIN devices d ON e.device_id = d.id
        WHERE e.timestamp >= ? AND e.timestamp <= ?
    """
    params = [start_iso, end_iso]
    if user_id:
        sql += " AND e.employee_id = ?"
        params.append(user_id)
    if device_id:
        sql += " AND e.device_id = ?"
        params.append(device_id)
    sql += " ORDER BY e.employee_id, e.timestamp ASC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows
