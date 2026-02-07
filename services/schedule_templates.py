import sqlite3
import os
from datetime import time
from db import get_conn

DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_hhmm(val: str) -> time:
    h, m = val.split(":")
    return time(int(h), int(m))


# -------------------------------------------------
# Templates
# -------------------------------------------------

def list_templates():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, name, description
        FROM schedule_templates
        ORDER BY name
        """
    ).fetchall()

    conn.close()

    # Convert rows to dicts so Jinja can use .id, .name, etc.
    return [dict(r) for r in rows]


# -------------------------------------------------
# APPLY TEMPLATE TO  USER  THIS WAS MISSING
# -------------------------------------------------

def assign_template_to_user(employee_id: str, template_id: int | None):
    conn = get_conn()
    cur = conn.cursor()

    row = cur.execute(
        "SELECT id FROM users WHERE employee_id = ?",
        (str(employee_id),),
    ).fetchone()

    if not row:
        conn.close()
        return

    user_id = row["id"]

    if template_id is None:
        cur.execute(
            "DELETE FROM user_schedule_assignments WHERE user_id = ?",
            (user_id,),
        )
    else:
        cur.execute(
            """
            INSERT OR REPLACE INTO user_schedule_assignments
                (user_id, template_id, assigned_at)
            VALUES (?, ?, datetime('now'))
            """,
            (user_id, template_id),
        )

    conn.commit()
    conn.close()



def get_user_schedule(employee_id: str, weekday: int):
    """
    Resolve schedule for an employee_id on a given weekday
    using the NEW template-based system.
    """
    conn = get_conn()
    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT
            td.start_time,
            td.end_time,
            td.daily_hours,
            td.auto_heal,
            td.allow_overtime,
            td.grace_in_minutes,
            td.grace_out_minutes
        FROM users u
        JOIN user_schedule_assignments usa
            ON usa.user_id = u.id
        JOIN schedule_template_days td
            ON td.template_id = usa.template_id
        WHERE u.employee_id = ?
          AND td.weekday = ?
        """,
        (str(employee_id), int(weekday)),
    ).fetchone()

    conn.close()

    if not row:
        return None

    return {
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "daily_hours": row["daily_hours"],
        "auto_heal": row["auto_heal"],
        "allow_overtime": row["allow_overtime"],
        "grace_in_minutes": row["grace_in_minutes"],
        "grace_out_minutes": row["grace_out_minutes"],
    }

def rebuild_template_days(template_id: int):
    conn = get_conn()
    cur = conn.cursor()

    # Clear old expansion
    cur.execute(
        "DELETE FROM schedule_template_days WHERE template_id = ?",
        (template_id,)
    )

    # Rebuild from rules + shifts
    cur.execute("""
        INSERT INTO schedule_template_days (
            template_id,
            weekday,
            start_time,
            end_time,
            daily_hours,
            auto_heal,
            allow_overtime,
            grace_in_minutes,
            grace_out_minutes
        )
        SELECT
            r.template_id,
            CAST(d.weekday AS INTEGER),
            s.start_time,
            s.end_time,
            CAST(
              (strftime('%s', s.end_time) - strftime('%s', s.start_time)) / 3600
              AS INTEGER
            ),
            1, 1, 0, 0
        FROM schedule_rules r
        JOIN schedule_shifts s ON s.rule_id = r.id
        JOIN (
            SELECT '0' AS weekday UNION
            SELECT '1' UNION
            SELECT '2' UNION
            SELECT '3' UNION
            SELECT '4' UNION
            SELECT '5' UNION
            SELECT '6'
        ) d
        WHERE r.template_id = ?
          AND instr(',' || r.weekdays || ',', ',' || d.weekday || ',') > 0
    """, (template_id,))

    conn.commit()
    conn.close()

def ensure_template_days_exist(template_id: int):
    """
    Defensive guard:
    If a template has rules/shifts but no materialized days,
    rebuild automatically.
    """
    conn = get_conn()
    cur = conn.cursor()

    has_rules = cur.execute(
        "SELECT 1 FROM schedule_rules WHERE template_id = ? LIMIT 1",
        (template_id,)
    ).fetchone()

    has_days = cur.execute(
        "SELECT 1 FROM schedule_template_days WHERE template_id = ? LIMIT 1",
        (template_id,)
    ).fetchone()

    conn.close()

    if has_rules and not has_days:
        rebuild_template_days(template_id)


def ensure_template_days_exist_for_user(employee_id: str):
    conn = get_conn()
    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT usa.template_id
        FROM users u
        JOIN user_schedule_assignments usa ON usa.user_id = u.id
        WHERE u.employee_id = ?
        """,
        (employee_id,)
    ).fetchone()

    conn.close()

    if row and row["template_id"]:
        ensure_template_days_exist(row["template_id"])
