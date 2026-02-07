# routes/daily_audit.py

from flask import Blueprint, render_template, request, g, Response
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import csv
import io

from db import list_devices
from services.query_helpers import query_events_range
from services.user_helpers import list_users

from authz import login_required, role_required

bp = Blueprint("daily_audit", __name__, url_prefix="/audit")

DUPLICATE_WINDOW_SECONDS = 60
ALLOWED_ROLES = {"admin", "supervisor"}


def _list_users():
    from db import get_conn
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT employee_id, name
        FROM events
        ORDER BY name
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def _audit_access_allowed():
    role = getattr(g, "user_role", None)
    return True if role is None else role in ALLOWED_ROLES


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _mark_duplicates(events):
    events.sort(key=lambda e: e["dt"])
    prev = None
    for e in events:
        e["duplicate"] = False
        if prev and (e["dt"] - prev["dt"]).total_seconds() <= DUPLICATE_WINDOW_SECONDS:
            e["duplicate"] = True
        prev = e
    return events


@bp.route("/daily", methods=["GET"])
@login_required
@role_required
def daily_audit():
    if not _audit_access_allowed():
        return "Forbidden", 403

    T = g.T

    raw_date = request.args.get("date")
    user = request.args.get("user") or None
    device = request.args.get("device") or None

    selected_date = _parse_date(raw_date) or datetime.now().date()

    # 🔥 IMPORTANT FIX: query with buffer
    query_start = datetime.combine(selected_date - timedelta(days=1), time.min)
    query_end   = datetime.combine(selected_date + timedelta(days=1), time.max)

    rows = query_events_range(
        query_start.isoformat(" "),
        query_end.isoformat(" "),
        user,
        device,
    )

    grouped = defaultdict(lambda: {"name": None, "events": []})

    for r in rows:
        emp_id = r[2]
        emp_name = r[3]
        ts_str = r[4]
        device_name = r[6] if len(r) > 6 else "-"

        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            continue

        # ✅ Filter by LOCAL date here
        if ts.date() != selected_date:
            continue

        grouped[emp_id]["name"] = emp_name
        grouped[emp_id]["events"].append({
            "dt": ts,
            "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "device": device_name,
        })

    for emp_id in grouped:
        grouped[emp_id]["events"] = _mark_duplicates(grouped[emp_id]["events"])

    return render_template(
        "daily_audit.html",
        T=T,
        selected_date=selected_date.isoformat(),
        data=grouped,
        devices=list_devices(),
        users=_list_users(),
        selected_user=user,
        selected_device=device,
    )


@bp.route("/daily/export", methods=["GET"])
def daily_audit_export():
    if not _audit_access_allowed():
        return "Forbidden", 403

    raw_date = request.args.get("date")
    user = request.args.get("user") or None
    device = request.args.get("device") or None

    selected_date = _parse_date(raw_date)
    if not selected_date:
        return "Invalid date", 400

    query_start = datetime.combine(selected_date - timedelta(days=1), time.min)
    query_end   = datetime.combine(selected_date + timedelta(days=1), time.max)

    rows = query_events_range(
        query_start.isoformat(" "),
        query_end.isoformat(" "),
        user,
        device,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee ID", "Employee Name", "Timestamp", "Device"])

    for r in rows:
        ts = datetime.fromisoformat(r[4])
        if ts.date() != selected_date:
            continue

        writer.writerow([
            r[2],
            r[3],
            r[4],
            r[6] if len(r) > 6 else "-",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=audit_{selected_date.isoformat()}.csv"
        },
    )
