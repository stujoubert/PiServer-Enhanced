#!/usr/bin/env python3
import os
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime_text import MIMEText
from email.mime.application import MIMEApplication

from openpyxl import Workbook

DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def get_setting(key, default=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default

def compute_weekly_hours():
    today = datetime.now()
    start = today - timedelta(days=today.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT employee_id, name, timestamp, type
           FROM events
           WHERE timestamp >= ? AND timestamp <= ?
           ORDER BY employee_id, timestamp ASC""",
        (start.isoformat(), end.isoformat()),
    )
    rows = cur.fetchall()
    conn.close()
    users = {}
    for emp, name, ts, evtype in rows:
        users.setdefault(emp, {"employee_id": emp, "name": name, "ins": 0, "outs": 0, "events": []})
        users[emp]["events"].append((ts, evtype))
        if evtype == "IN":
            users[emp]["ins"] += 1
        elif evtype == "OUT":
            users[emp]["outs"] += 1
    for emp, data in users.items():
        events = data["events"]
        hours = 0.0
        last_in = None
        for ts, evtype in events:
            t = datetime.fromisoformat(ts)
            if evtype == "IN":
                last_in = t
            elif evtype == "OUT" and last_in:
                hours += (t - last_in).total_seconds() / 3600.0
                last_in = None
        data["hours"] = round(hours, 2)
    return users, start, end

def build_excel(users):
    wb = Workbook()
    ws = wb.active
    ws.title = "Weekly Hours"
    ws.append(["Employee ID", "Name", "Total IN", "Total OUT", "Hours Worked"])
    for emp in users.values():
        ws.append([
            emp["employee_id"],
            emp["name"],
            emp["ins"],
            emp["outs"],
            emp["hours"],
        ])
    from io import BytesIO
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

def send_weekly_email():
    smtp_sender = get_setting("smtp_sender", "")
    smtp_host = get_setting("smtp_host", "smtp.gmail.com")
    smtp_port = int(get_setting("smtp_port", "587") or 587)
    smtp_pass = get_setting("smtp_pass", "")
    recipient = get_setting("report_recipient", smtp_sender)
    if not smtp_sender or not smtp_pass or not recipient:
        print("SMTP not fully configured.")
        return
    users, start, end = compute_weekly_hours()
    xlsx_buf = build_excel(users)
    msg = MIMEMultipart()
    msg["From"] = smtp_sender
    msg["To"] = recipient
    msg["Subject"] = f"Weekly Attendance Hours ({start.date()} to {end.date()})"
    body = (
        f"Weekly attendance hours report attached.\n\n"
        f"Period: {start.date()} to {end.date()}\n"
        f"Users: {len(users)}"
    )
    msg.attach(MIMEText(body, "plain"))
    part = MIMEApplication(xlsx_buf.read(), Name="weekly_hours.xlsx")
    part["Content-Disposition"] = 'attachment; filename="weekly_hours.xlsx"'
    msg.attach(part)
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_sender, smtp_pass)
        server.send_message(msg)
        server.quit()
        print("Weekly email sent to", recipient)
    except Exception as exc:
        print("Error sending weekly email:", exc)

if __name__ == "__main__":
    send_weekly_email()
