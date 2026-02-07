#!/usr/bin/env python3
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Set

DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ----------------------------
# DB helpers
# ----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ----------------------------
# Weekday parsing (robust)
# Supports:
#  - "0,1,2,3,4"  (Mon=0 ... Sun=6)
#  - "0 1 2 3 4"
#  - "MON,TUE,WED" / "Mon Tue"
#  - "MTWRFSU" (Mon Tue Wed Thu Fri Sat Sun)
#  - "MTWTF" (legacy-ish; NOTE: ambiguous Thu vs Tue; avoid)
# Recommended canonical storage: "MTWRFSU" or numeric list.
# ----------------------------
_CANON = {
    "MON": 0, "MO": 0, "M": 0,
    "TUE": 1, "TU": 1, "T": 1,
    "WED": 2, "WE": 2, "W": 2,
    "THU": 3, "TH": 3, "R": 3,
    "FRI": 4, "FR": 4, "F": 4,
    "SAT": 5, "SA": 5, "S": 5,
    "SUN": 6, "SU": 6, "U": 6,
}


def parse_weekdays(weekdays_text: str) -> Set[int]:
    if not weekdays_text:
        return set()

    s = weekdays_text.strip().upper()

    # Numeric formats: "0,1,2" or "0 1 2"
    if any(ch.isdigit() for ch in s):
        parts = [p for p in s.replace(",", " ").split() if p]
        out = set()
        for p in parts:
            try:
                n = int(p)
            except Exception:
                continue
            if 0 <= n <= 6:
                out.add(n)
        return out

    # Token formats with separators: "MON,TUE" "Mon Tue"
    if "," in s or " " in s:
        parts = [p for p in s.replace(",", " ").split() if p]
        out = set()
        for p in parts:
            if p in _CANON:
                out.add(_CANON[p])
        return out

    # Compact letter format: "MTWRFSU"
    # We scan from left to right and accept known single-letter codes
    # (M,T,W,R,F,S,U). This avoids ambiguity.
    out = set()
    for ch in s:
        if ch in _CANON:
            out.add(_CANON[ch])
    return out


# ----------------------------
# Core: resolve shifts for a user + date
# ----------------------------
def get_user_schedule_template_id(employee_id: str) -> Optional[int]:
    conn = get_conn()
    row = conn.execute(
        "SELECT schedule_template_id FROM users WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    tid = row["schedule_template_id"]
    return int(tid) if tid is not None else None


def get_template_rules(template_id: int) -> List[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, template_id, weekdays, priority
        FROM schedule_rules
        WHERE template_id = ?
        ORDER BY priority ASC, id ASC
        """,
        (template_id,)
    ).fetchall()
    conn.close()
    return rows


def get_rule_shifts(rule_id: int) -> List[sqlite3.Row]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, rule_id, start_time, end_time, grace_minutes, break_minutes
        FROM schedule_shifts
        WHERE rule_id = ?
        ORDER BY start_time ASC, end_time ASC, id ASC
        """,
        (rule_id,)
    ).fetchall()
    conn.close()
    return rows


def get_expected_shifts_for_user(employee_id: str, day: date) -> List[Dict]:
    """
    Returns a list of shifts that apply to the employee on 'day', using:
      users.schedule_template_id -> schedule_rules (weekday match) -> schedule_shifts

    Output is normalized dicts:
      {
        "template_id": int,
        "rule_id": int,
        "shift_id": int,
        "start_time": "HH:MM",
        "end_time": "HH:MM",
        "grace_minutes": int,
        "break_minutes": int
      }

    If no advanced schedule is assigned or no rules match, returns [].
    """
    template_id = get_user_schedule_template_id(employee_id)
    if not template_id:
        return []

    weekday = day.weekday()  # Mon=0 ... Sun=6

    matched = []
    rules = get_template_rules(template_id)
    for r in rules:
        wset = parse_weekdays(r["weekdays"])
        if weekday not in wset:
            continue

        shifts = get_rule_shifts(r["id"])
        for sh in shifts:
            matched.append({
                "template_id": template_id,
                "rule_id": int(r["id"]),
                "shift_id": int(sh["id"]),
                "start_time": sh["start_time"],
                "end_time": sh["end_time"],
                "grace_minutes": int(sh["grace_minutes"] or 0),
                "break_minutes": int(sh["break_minutes"] or 0),
            })

    return matched


# ----------------------------
# Convenience: compute datetime windows (optional helper)
# ----------------------------
def shift_datetimes(day: date, start_hhmm: str, end_hhmm: str):
    """
    Returns (start_dt, end_dt). Supports overnight shifts where end < start.
    """
    start_dt = datetime.combine(day, datetime.strptime(start_hhmm, "%H:%M").time())
    end_dt = datetime.combine(day, datetime.strptime(end_hhmm, "%H:%M").time())
    if end_dt <= start_dt:
        # Overnight shift
        end_dt = end_dt.replace(day=day.day)  # no-op; clarity
        end_dt = end_dt + (datetime.combine(day, datetime.min.time()) - datetime.combine(day, datetime.min.time()))
        end_dt = end_dt.replace()  # no-op
        end_dt = end_dt + (datetime.combine(day, datetime.min.time()) - datetime.combine(day, datetime.min.time()))
        # Simpler:
        from datetime import timedelta
        end_dt = end_dt + timedelta(days=1)
    return start_dt, end_dt


def build_weekly_grid(template_id: int):
    """
    Returns a structure suitable for a weekly grid UI.
    """
    conn = get_conn()

    rules = conn.execute(
        """
        SELECT r.id, r.weekdays, s.start_time, s.end_time
        FROM schedule_rules r
        JOIN schedule_shifts s ON s.rule_id = r.id
        WHERE r.template_id = ?
        ORDER BY r.priority, s.start_time
        """,
        (template_id,),
    ).fetchall()

    conn.close()

    grid = {d: [] for d in WEEKDAYS}

    for r in rules:
        days = parse_weekdays(r["weekdays"])
        for idx, label in enumerate(WEEKDAYS):
            if idx in days:
                grid[label].append(
                    f'{r["start_time"]} – {r["end_time"]}'
                )

    return grid
