import os
import sqlite3


def get_db_path():
    db_path = os.environ.get("ATT_DB")
    if not db_path:
        raise RuntimeError(
            "ATT_DB environment variable is not set. "
            "Refusing to start without explicit database path."
        )
    return db_path


def get_conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def list_devices():
    """
    Return all devices from the devices table.
    Dev-safe: returns empty list if table does not exist.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        rows = cur.execute(
            "SELECT * FROM devices ORDER BY id"
        ).fetchall()
        return rows
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_setting(key, default=None):
    """
    Fetch a setting value from the settings table.
    Returns default if table or key does not exist.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        row = cur.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row:
            return row["value"]
        return default
    except sqlite3.OperationalError:
        # settings table does not exist (dev / fresh schema)
        return default
    finally:
        conn.close()
