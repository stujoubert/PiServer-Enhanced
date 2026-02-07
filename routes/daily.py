#!/usr/bin/env python3
# routes/daily.py

from __future__ import annotations

from flask import Blueprint, render_template, request, g
from datetime import datetime, time
from db import get_conn, list_devices

from authz import login_required, role_required

bp = Blueprint("daily", __name__, url_prefix="/daily")


def _events_columns(conn) -> set[str]:
    rows = conn.execute("PRAGMA table_info(events)").fetchall()
    # sqlite Row or tuple support both
    out = set()
    for r in rows:
        try:
            out.add(r["name"])
        except Exception:
            out.add(r[1])
    return out


def query_events_daily(day_str: str, user: str | None = None, device: str | None = None):
    """
    day_str: 'YYYY-MM-DD' in LOCAL time.
    Uses datetime(timestamp,'localtime') so ISO offsets are handled correctly.
    """
    conn = get_conn()
    cur = conn.cursor()

    cols = _events_columns(conn)

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
        WHERE date(datetime(e.timestamp,'localtime')) = ?
    """
    params = [day_str]

    if user:
        sql += " AND e.employee_id = ?"
        params.append(user)

    if device:
        sql += " AND e.device_id = ?"
        params.append(device)

    sql += " ORDER BY e.employee_id, datetime(e.timestamp,'localtime') ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


@bp.route("/", methods=["GET"], endpoint="daily")
@login_required
@role_required("viewer", "manager", "admin")
def daily_view():
    T = g.T
    user = request.args.get("user") or None
    device = request.args.get("device") or None

    date_param = request.args.get("date")
    if date_param:
        try:
            day = datetime.fromisoformat(date_param).date()
        except Exception:
            day = datetime.now().date()
    else:
        day = datetime.now().date()

    rows = query_events_daily(day.isoformat(), user, device)

    # group events by employee_id
    grouped = {}
    for r in rows:
        # Row may be tuple depending on db.get_conn; support both
        try:
            emp_id = r["employee_id"]
            name = r["name"]
        except Exception:
            emp_id = r[2]
            name = r[3]

        grouped.setdefault(emp_id, {"name": name, "events": []})
        grouped[emp_id]["events"].append(r)

    return render_template(
        "index.html",
        title=T.get("daily_attendance", "Daily Attendance"),
        rows=rows,
        grouped=grouped,
        devices=list_devices(),
        selected_user=user,
        selected_device=device,
        daily_date=day.isoformat(),
        week_start=None,
        week_end=None,
    )
