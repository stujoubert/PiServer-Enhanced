# routes/weekly.py

from flask import Blueprint, render_template, request, g
from datetime import datetime
from collections import defaultdict

from db import list_devices
from attendance_services import build_week_list, get_week_bounds_from_type
from services.query_helpers import query_events_range
from attendance.calc import calculate_daily_attendance
from services.user_helpers import list_users

from authz import login_required, role_required

bp = Blueprint("weekly", __name__, url_prefix="/weekly")


@bp.route("/", methods=["GET"])
@login_required
@role_required("viewer", "manager", "admin")
def weekly_view():
    T = g.T

    week_type = request.args.get("week_type", "mon_fri")
    week_param = request.args.get("week")
    user = request.args.get("user") or None
    device = request.args.get("device") or None

    today = datetime.now().date()

    # Resolve week start
    if week_param:
        try:
            selected_date = datetime.fromisoformat(week_param).date()
        except Exception:
            selected_date = today
    else:
        selected_date = today

    week_start, week_end = get_week_bounds_from_type(selected_date, week_type)

    week_list = build_week_list(week_type, today, T)

    start_iso = f"{week_start} 00:00:00"
    end_iso = f"{week_end} 23:59:59"

    rows = query_events_range(start_iso, end_iso, user, device)

    grouped = defaultdict(lambda: {
        "name": None,
        "days": defaultdict(list),
    })

    for r in rows:
        # sqlite3.Row MUST be accessed by index or key — never .get()
        emp_id = r["employee_id"]
        ts_str = r["timestamp"]

        if not emp_id or not ts_str:
            continue

        try:
            ts = datetime.fromisoformat(ts_str[:19])
        except Exception:
            continue

        day = ts.date()

        grouped[emp_id]["name"] = r["name"]
        grouped[emp_id]["days"][day].append({
            "user_id": emp_id,
            "event_time": ts,
        })

    weekly_summary = {}
    anomalies = []

    for emp_id, data in grouped.items():
        days_out = {}

        for day, events in data["days"].items():
            att = calculate_daily_attendance(events)
            if not att:
                continue

            rec = {
                "in": att["in"].strftime("%Y-%m-%d %H:%M:%S") if att["in"] else None,
                "out": att["out"].strftime("%Y-%m-%d %H:%M:%S") if att["out"] else None,
                "hours": round(att["worked_seconds"] / 3600, 2),
                "punches": att["punch_count"],
                "flags": att["flags"],
            }

            day_key = day.isoformat()
            days_out[day_key] = rec

            if rec["flags"]:
                anomalies.append({
                    "emp_id": emp_id,
                    "name": data["name"],
                    "day": day_key,
                    "in": rec["in"],
                    "out": rec["out"],
                    "hours": rec["hours"],
                    "punches": rec["punches"],
                    "flags": rec["flags"],
                })

        weekly_summary[emp_id] = {
            "name": data["name"],
            "days": days_out,
        }

    anomalies.sort(key=lambda x: (x["day"], x["emp_id"]))

    return render_template(
        "weekly.html",
        T=T,
        week_type=week_type,
        week_list=week_list,
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        summary=weekly_summary,
        anomalies=anomalies,
        devices=list_devices(),
        users=list_users(),
        selected_user=user,
        selected_device=device,
    )
