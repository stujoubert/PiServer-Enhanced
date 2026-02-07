def build_weekly_payroll(daily_attendance, week_dates):
    payroll = {}

    for user_id, days in daily_attendance.items():
        total_seconds = 0
        flags = []

        for d in week_dates:
            day = days.get(d)
            if not day:
                continue

            total_seconds += day["worked_seconds"]
            flags.extend(day["flags"])

        payroll[user_id] = {
            "worked_seconds": total_seconds,
            "worked_hours": round(total_seconds / 3600, 2),
            "flags": list(set(flags)),
        }

    return payroll
