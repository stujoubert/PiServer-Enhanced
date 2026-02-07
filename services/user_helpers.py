# services/user_helpers.py

from db import get_conn
from functools import lru_cache


@lru_cache(maxsize=1)
def list_users():
    """
    Returns list of (employee_id, display_name)
    Cached to avoid repeated DB hits.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT employee_id, MAX(name) as name
        FROM events
        GROUP BY employee_id
        ORDER BY name
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def clear_user_cache():
    list_users.cache_clear()
