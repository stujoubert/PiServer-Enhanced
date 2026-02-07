#!/usr/bin/env python3
# services/query_helpers.py

from __future__ import annotations

import os
import sqlite3
from typing import Iterable, List, Optional, Sequence, Tuple

DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def query_events_range(
    start_local: str,
    end_local: str,
    user: Optional[str] = None,
    device: Optional[str] = None,
) -> List[sqlite3.Row]:
    """
    Range query for events using LOCAL time boundaries.
    - start_local / end_local should be like: 'YYYY-MM-DD HH:MM:SS'
    - Works with ISO timestamps that include timezone offsets.
    - Does NOT assume optional columns exist.
    """
    conn = _get_conn()
    cols = _table_columns(conn, "events")

    # Select only what exists.
    select_cols = [
        "e.id",
        "e.device_id",
        "e.employee_id",
        "e.name",
        "e.timestamp",
    ]
    if "type" in cols:
        select_cols.append("e.type")
    if "direction" in cols:
        select_cols.append("e.direction")
    if "picture_url" in cols:
        select_cols.append("e.picture_url")

    sql = f"""
        SELECT {", ".join(select_cols)}, d.name AS device_name
        FROM events e
        LEFT JOIN devices d ON e.device_id = d.id
        WHERE datetime(e.timestamp, 'localtime')
              BETWEEN datetime(?) AND datetime(?)
    """
    params: List[object] = [start_local, end_local]

    if user:
        sql += " AND e.employee_id = ?"
        params.append(user)

    if device:
        sql += " AND e.device_id = ?"
        params.append(device)

    sql += """
        ORDER BY
            e.employee_id,
            datetime(e.timestamp, 'localtime') ASC
    """

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows
