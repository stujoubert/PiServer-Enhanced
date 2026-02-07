# attendance_services.py
from datetime import datetime, timedelta, date
from dateutil import parser
from db import get_conn, get_setting
from translations import LANG

def normalize_ts(ts: str) -> str:
    try:
        if "-" in ts[10:]:
            base = ts.split("-")[0]
            dt = datetime.fromisoformat(base)
        else:
            dt = datetime.fromisoformat(ts.replace("T", " "))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        ts = ts.replace("T", " ").split("Z")[0]
        return ts


def calculate_hours(first_in, last_out, employee_id=None, get_shift=None):
    if not first_in or not last_out:
        return 0.0, 0.0

    dt_in = datetime.fromisoformat(first_in)
    dt_out = datetime.fromisoformat(last_out)

    work_day = dt_in.date()

    shift = None
    if employee_id and get_shift:
        try:
            shift = get_shift(employee_id, work_day)
        except Exception:
            shift = None

    if shift:
        expected_start = shift["start_time"]
        expected_end   = shift["end_time"]
        break_minutes  = shift.get("break_minutes", 0)
        overnight      = shift.get("overnight", 0)
    else:
        expected_start = get_setting("work_start_time", "08:00")
        expected_end   = get_setting("work_end_time", "17:00")
        break_minutes  = 0
        overnight      = 0

    ws_hour, ws_min = map(int, expected_start.split(":"))
    we_hour, we_min = map(int, expected_end.split(":"))

    ws_dt = dt_in.replace(hour=ws_hour, minute=ws_min, second=0)
    we_dt = dt_in.replace(hour=we_hour, minute=we_min, second=0)

    if overnight and we_dt <= ws_dt:
        we_dt += timedelta(days=1)

    total_hours = max(0.0, (dt_out - dt_in).total_seconds() / 3600.0)

    reg_start = max(dt_in, ws_dt)
    reg_end   = min(dt_out, we_dt)

    regular_hours = max(0.0, (reg_end - reg_start).total_seconds() / 3600.0)

    if break_minutes > 0:
        regular_hours -= (break_minutes / 60)
        regular_hours = max(0.0, regular_hours)

    overtime_hours = max(0.0, total_hours - regular_hours)
    return round(regular_hours, 2), round(overtime_hours, 2)


def get_first_in_last_out(start: datetime, end: datetime):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, name, timestamp, type
        FROM events
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
        ORDER BY employee_id, timestamp ASC
        """,
        (start.date().isoformat(), end.date().isoformat()),
    )
    rows = cur.fetchall()
    conn.close()

    result = {}
    for emp, name, ts, evtype in rows:
        try:
            dt = parser.parse(ts)
        except Exception:
            continue

        day = dt.date().isoformat()

        if emp not in result:
            result[emp] = {"name": name, "days": {}, "total_hours": 0.0}
        if day not in result[emp]["days"]:
            result[emp]["days"][day] = {"in": None, "out": None, "hours": 0.0}

        rec = result[emp]["days"][day]

        if evtype == "IN":
            if rec["in"] is None or dt < parser.parse(rec["in"]):
                rec["in"] = dt.isoformat()
        elif evtype == "OUT":
            if rec["out"] is None or dt > parser.parse(rec["out"]):
                rec["out"] = dt.isoformat()

    for emp, data in result.items():
        total = 0.0
        for day, rec in data["days"].items():
            if rec["in"] and rec["out"]:
                try:
                    t1 = parser.parse(rec["in"])
                    t2 = parser.parse(rec["out"])
                    hrs = max(0.0, (t2 - t1).total_seconds() / 3600.0)
                except Exception:
                    hrs = 0.0
            else:
                hrs = 0.0
            rec["hours"] = round(hrs, 2)
            total += hrs
        data["total_hours"] = round(total, 2)

    return result


def build_week_list(week_type, today, T):
    """
    Returns a list of past 12 weeks:
    [
        (week_start_iso, week_end_iso, "Dec 06 → Dec 12"),
        ...
    ]
    """
    weeks = []
    base = today

    for i in range(12):
        # Move backwards by weekly intervals
        offset_date = base - timedelta(days=i * 7)

        ws, we = get_week_bounds_from_type(offset_date, week_type)

        # Human readable label
        label = f"{ws.strftime('%b %d')} → {we.strftime('%b %d')}"

        # Return tuple
        weeks.append((ws.isoformat(), we.isoformat(), label))

    return weeks



def get_week_bounds_from_type(base_date: date, week_type: str):
    wd = base_date.weekday()
    if week_type == "sat_fri":
        start = base_date - timedelta(days=(wd - 5) % 7)
        end   = start + timedelta(days=6)
    elif week_type == "mon_fri":
        start = base_date - timedelta(days=wd)
        end   = start + timedelta(days=4)
    elif week_type == "mon_sat":
        start = base_date - timedelta(days=wd)
        end   = start + timedelta(days=5)
    elif week_type == "sun_sat":
        start = base_date - timedelta(days=(wd + 1) % 7)
        end   = start + timedelta(days=6)
    else:
        start = base_date - timedelta(days=(wd - 5) % 7)
        end   = start + timedelta(days=6)
    return start, end
