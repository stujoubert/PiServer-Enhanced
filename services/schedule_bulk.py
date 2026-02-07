from services.schedules import get_conn

def apply_template_to_users(template_id, user_ids, overwrite=True):
    conn = get_conn()
    cur = conn.cursor()

    # Load template days
    template_days = cur.execute("""
        SELECT weekday, start_time, end_time, daily_hours,
               auto_heal, allow_overtime, grace_in_minutes, grace_out_minutes
        FROM schedule_template_days
        WHERE template_id = ?
    """, (template_id,)).fetchall()

    for user_id in user_ids:
        for row in template_days:
            if overwrite:
                cur.execute("""
                    DELETE FROM user_schedules
                    WHERE employee_id = ? AND weekday = ?
                """, (user_id, row["weekday"]))

            cur.execute("""
                INSERT OR REPLACE INTO user_schedules (
                    employee_id, weekday, start_time, end_time,
                    daily_hours, auto_heal, allow_overtime,
                    grace_in_minutes, grace_out_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                row["weekday"],
                row["start_time"],
                row["end_time"],
                row["daily_hours"],
                row["auto_heal"],
                row["allow_overtime"],
                row["grace_in_minutes"],
                row["grace_out_minutes"],
            ))

    conn.commit()
    conn.close()
