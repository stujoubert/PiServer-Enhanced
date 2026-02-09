from flask import Blueprint, render_template, request, g
from datetime import date, datetime, time
from calendar import monthrange

from db import get_conn
from services.schedule_templates import get_user_schedule
from authz import login_required

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _parse_time(value):
    if not value:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            if len(value) == 5:
                return datetime.strptime(value, "%H:%M").time()
            return datetime.strptime(value, "%H:%M:%S").time()
        except Exception:
            return None
    return None


# --------------------------------------------------
# Routes
# --------------------------------------------------

@bp.route("/", methods=["GET"])
@login_required
def dashboard():
    selected_date = request.args.get("date") or date.today().isoformat()
    selected_dt = datetime.fromisoformat(selected_date)
    weekday = selected_dt.weekday()

    conn = get_conn()
    cur = conn.cursor()

    # --------------------------------------------------
    # DAILY SUMMARY (CANONICAL SOURCE: events)
    # --------------------------------------------------

    expected = cur.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    daily_rows = cur.execute("""
        SELECT
            e.employee_id,
            COALESCE(u.name, e.employee_id) AS name,
            MIN(e.timestamp) AS first_event,
            MAX(e.timestamp) AS last_event,
            COUNT(*) AS event_count
        FROM events e
        LEFT JOIN users u
            ON u.employee_id = e.employee_id
        WHERE DATE(e.timestamp) = ?
        GROUP BY e.employee_id
    """, (selected_date,)).fetchall()

    attended = len(daily_rows)
    present = attended
    absent = max(expected - attended, 0)

    late = 0
    early_leave = 0
    missed = 0

    for r in daily_rows:
        schedule = get_user_schedule(r["employee_id"], weekday)
        if not schedule:
            continue

        sched_start = _parse_time(schedule.get("start_time"))
        sched_end = _parse_time(schedule.get("end_time"))

        try:
            first_dt = datetime.fromisoformat(r["first_event"])
            last_dt = datetime.fromisoformat(r["last_event"])
        except Exception:
            continue

        if sched_start and first_dt.time() > sched_start:
            late += 1
        if sched_end and last_dt.time() < sched_end:
            early_leave += 1
        if r["event_count"] == 1:
            missed += 1

    attendance_rate = (
        round((attended / expected) * 100, 1)
        if expected else 0
    )

    # --------------------------------------------------
    # MONTHLY SUMMARY (CANONICAL SOURCE: events)
    # --------------------------------------------------

    year = selected_dt.year
    month = selected_dt.month
    days_in_month = monthrange(year, month)[1]

    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{days_in_month}"

    monthly_rows = cur.execute("""
        SELECT
            e.employee_id,
            COALESCE(u.name, e.employee_id) AS name,
            DATE(e.timestamp) AS day,
            COUNT(*) AS event_count,
            MIN(e.timestamp) AS first_event,
            MAX(e.timestamp) AS last_event
        FROM events e
        LEFT JOIN users u
            ON u.employee_id = e.employee_id
        WHERE DATE(e.timestamp) BETWEEN ? AND ?
        GROUP BY e.employee_id, day
    """, (month_start, month_end)).fetchall()

    monthly = {}

    for r in monthly_rows:
        emp = r["employee_id"]
        name = r["name"]
        day = r["day"]
        weekday = datetime.fromisoformat(day).weekday()

        if emp not in monthly:
            monthly[emp] = {
                "employee_id": emp,
                "name": name,
                "attended": 0,
                "late": 0,
                "early": 0,
                "missed": 0,
            }

        monthly[emp]["attended"] += 1

        schedule = get_user_schedule(emp, weekday)
        if not schedule:
            continue

        sched_start = _parse_time(schedule.get("start_time"))
        sched_end = _parse_time(schedule.get("end_time"))

        try:
            first_dt = datetime.fromisoformat(r["first_event"])
            last_dt = datetime.fromisoformat(r["last_event"])
        except Exception:
            continue

        if sched_start and first_dt.time() > sched_start:
            monthly[emp]["late"] += 1
        if sched_end and last_dt.time() < sched_end:
            monthly[emp]["early"] += 1
        if r["event_count"] == 1:
            monthly[emp]["missed"] += 1

    monthly_list = []
    for m in monthly.values():
        m["rate"] = round((m["attended"] / days_in_month) * 100, 1)
        monthly_list.append(m)

    monthly_list.sort(
        key=lambda x: int(x["employee_id"])
        if str(x["employee_id"]).isdigit()
        else x["employee_id"]
    )

    # --------------------------------------------------
    # LOCALIZED MONTH LABEL
    # --------------------------------------------------

    months = g.T.get("months_short", [])
    if months and 1 <= month <= len(months):
        month_label = f"{months[month - 1]} {year}"
    else:
        month_label = selected_dt.strftime("%B %Y")

    conn.close()

    return render_template(
        "dashboard_improved.html",
        selected_date=selected_date,
        expected=expected,
        attended=attended,
        absent=absent,
        present=present,
        late=late,
        early_leave=early_leave,
        missed=missed,
        attendance_rate=attendance_rate,
        monthly=monthly_list,
        month_label=month_label,
    )
