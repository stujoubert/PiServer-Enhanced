import sqlite3
import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, g
from db import get_conn, list_devices
from dateutil import parser as dtparser
from datetime import datetime, timedelta, time

from routes.payroll import (
    week_start_for,
    week_end_for,
    daterange,
    compute_payroll,
    build_week_list,
)

from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from services.users import (
    list_users,
    get_next_employee_id,
    save_user_face,
)


from authz import login_required, role_required
bp = Blueprint("users", __name__, url_prefix="/users")

# --------------------------------------------------
# List users (schema-tolerant)
# --------------------------------------------------
@bp.route("/", methods=["GET"])
@login_required
@role_required("admin")
def users_list():
    show_inactive = request.args.get("show_inactive") == "1"

    conn = get_conn()
    cur = conn.cursor()

    def _table_cols(table: str):
        try:
            return {r["name"] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        except Exception:
            return set()

    users_cols = _table_cols("users")
    du_cols = _table_cols("device_users")
    uf_cols = _table_cols("user_faces")

    # users active column drift: active vs is_active
    active_col = "is_active" if "is_active" in users_cols else ("active" if "active" in users_cols else None)

    # device_users link drift: employee_id vs user_id
    du_has_employee_id = "employee_id" in du_cols
    du_has_user_id = "user_id" in du_cols

    # user_faces drift: picture_url vs image_path and id existence
    uf_url_col = "picture_url" if "picture_url" in uf_cols else ("image_path" if "image_path" in uf_cols else None)
    uf_count_col = "id" if "id" in uf_cols else (uf_url_col if uf_url_col else "employee_id")

    # Build JOIN for device_users depending on schema
    device_join = ""
    if du_has_employee_id:
        # classic schema
        device_join = "LEFT JOIN device_users du ON du.employee_id = u.employee_id"
    elif du_has_user_id and "id" in users_cols:
        # newer schema linking by user_id
        device_join = "LEFT JOIN device_users du ON du.user_id = u.id"
    else:
        # if device_users doesn't match anything, still return users
        device_join = "LEFT JOIN device_users du ON 1=0"

    # devices join only if we can reach device_id
    devices_join = "LEFT JOIN devices d ON d.id = du.device_id" if "device_id" in du_cols else "LEFT JOIN devices d ON 1=0"

    # faces join
    faces_join = "LEFT JOIN user_faces uf ON uf.employee_id = u.employee_id" if "employee_id" in uf_cols else "LEFT JOIN user_faces uf ON 1=0"

    # Active filter
    where = []
    if (not show_inactive) and active_col:
        where.append(f"u.{active_col} = 1")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # Face URL expression (prefer /users/faces/... convention, fall back to stored path/url)
    face_url_expr = "NULL"
    if uf_url_col:
        face_url_expr = f"""
            MAX(
                CASE
                    WHEN uf.{uf_url_col} LIKE '/users/faces/%' THEN uf.{uf_url_col}
                    ELSE uf.{uf_url_col}
                END
            )
        """

    # Safe ordering: numeric employee_ids first, then text
    order_sql = """
        ORDER BY
            CASE
                WHEN u.employee_id GLOB '[0-9]*'
                THEN CAST(u.employee_id AS INTEGER)
                ELSE 999999999
            END,
            u.employee_id,
            u.id
    """ if "id" in users_cols else """
        ORDER BY
            CASE
                WHEN u.employee_id GLOB '[0-9]*'
                THEN CAST(u.employee_id AS INTEGER)
                ELSE 999999999
            END,
            u.employee_id
    """

    sql = f"""
        SELECT
            u.employee_id AS employee_id,
            u.name AS name,
            {f"u.{active_col}" if active_col else "1"} AS is_active,
            GROUP_CONCAT(DISTINCT d.name) AS device_name,
            COUNT(uf.{uf_count_col}) AS face_count,
            {face_url_expr} AS face_url
        FROM users u
        {device_join}
        {devices_join}
        {faces_join}
        {where_sql}
        GROUP BY u.employee_id, u.name, is_active
        {order_sql}
    """

    rows = cur.execute(sql).fetchall()
    conn.close()

    users = []
    for r in rows:
        users.append({
            "employee_id": r["employee_id"],
            "name": r["name"],
            "is_active": bool(r["is_active"]),
            "device_name": r["device_name"] or "",
            "face_count": int(r["face_count"] or 0),
            "face_url": r["face_url"],
        })

    return render_template(
        "users.html",
        users=users,
        show_inactive=show_inactive,
    )


# --------------------------------------------------
# FDLib bulk import
# --------------------------------------------------
@bp.route("/import-fdlib-faces", methods=["POST"])
def import_fdlib_faces():
    from collector import bulk_import_fdlib_faces
    from services.devices import get_primary_fdlib_device, touch_device_seen

    dev = get_primary_fdlib_device()
    if not dev:
        flash("No active FDLib device configured. Enable supports_fdlib on a device.", "danger")
        return redirect(url_for("users.users_list"))

    if not dev.get("ip") or not dev.get("username") or not dev.get("password"):
        flash("FDLib device is missing IP/username/password in Devices.", "danger")
        return redirect(url_for("users.users_list"))

    result = bulk_import_fdlib_faces(dev["ip"], dev["username"], dev["password"])

    try:
        touch_device_seen(int(dev["id"]))
    except Exception:
        pass

    # bulk_import_fdlib_faces in your repo sometimes returns dict; sometimes int.
    if isinstance(result, dict):
        imported = result.get("faces_imported", 0)
        flash(f"FDLib import complete. Imported: {imported}", "success")
    else:
        flash(f"FDLib import complete ({result} faces)", "success")

    return redirect(url_for("users.users_list"))


# --------------------------------------------------
# Resync users from device
# --------------------------------------------------
@bp.route("/resync-users", methods=["POST"])
def resync_users():
    from collector import sync_missing_users_from_device
    from services.devices import get_primary_fdlib_device, touch_device_seen

    dev = get_primary_fdlib_device()
    if not dev:
        flash("No active FDLib device configured. Enable supports_fdlib on a device.", "danger")
        return redirect(url_for("users.users_list"))

    if not dev.get("ip") or not dev.get("username") or not dev.get("password"):
        flash("FDLib device is missing IP/username/password in Devices.", "danger")
        return redirect(url_for("users.users_list"))

    result = sync_missing_users_from_device(dev["ip"], dev["username"], dev["password"])

    # If the call succeeded, record last_seen_at
    try:
        touch_device_seen(int(dev["id"]))
    except Exception:
        pass

    flash(
        f"User re-sync completed. Imported: {result.get('imported', 0)}, Skipped: {result.get('skipped', 0)}",
        "success",
    )
    return redirect(url_for("users.users_list"))


# --------------------------------------------------
# Promote snapshots
# --------------------------------------------------
@bp.route("/promote-snapshots", methods=["POST"])
def promote_snapshots_bulk():
    from collector import promote_event_snapshots_to_users, persist_promoted_event_faces

    limit = int(request.form.get("limit") or 50)
    result = promote_event_snapshots_to_users(limit)
    persisted = persist_promoted_event_faces()

    flash(
        f"Snapshot promotion completed. Imported: {result['imported']}, "
        f"Skipped: {result['skipped']}, Saved: {persisted}",
        "success",
    )

    return redirect(url_for("users.users_list"))

# --------------------------------------------------
# View user faces
# --------------------------------------------------
@bp.route("/<employee_id>/faces", methods=["GET"])
def user_faces(employee_id):
    conn = get_conn()
    cur = conn.cursor()

    faces = cur.execute("""
        SELECT picture_url, created_at
        FROM user_faces
        WHERE employee_id = ?
        ORDER BY created_at DESC
    """, (employee_id,)).fetchall()

    conn.close()

    return render_template("user_faces.html", employee_id=employee_id, faces=faces)

# --------------------------------------------------
# Serve cached face images
# --------------------------------------------------
@bp.route("/faces/<path:filename>")
def serve_face(filename):
    from flask import send_from_directory
    return send_from_directory(
        "/opt/attendance/static/uploads/device_faces",
        filename,
        as_attachment=False
    )


# --------------------------------------------------
# Add user
# --------------------------------------------------

@bp.route("/add", methods=["GET", "POST"])
@login_required
def users_add():

    if request.method == "POST":

        employee_id = request.form["employee_id"]
        name = request.form["name"]
        device_id = request.form["device_id"]

        # --------------------------------------------------
        # USER CREATION (INLINE SQL — EXISTING PATTERN)
        # --------------------------------------------------
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO users (employee_id, name, is_active)
            VALUES (?, ?, 1)
            """,
            (employee_id, name),
        )

        cur.execute(
            """
            INSERT INTO device_users (employee_id, device_id)
            VALUES (?, ?)
            """,
            (employee_id, device_id),
        )

        conn.commit()
        conn.close()

        # --------------------------------------------------
        # OPTIONAL FACE CAPTURE (NEW, SAFE)
        # --------------------------------------------------
        face_image = request.form.get("face_image")
        if face_image:
            try:
                save_user_face(employee_id, face_image)
            except Exception as e:
                flash(f"Face image could not be saved: {e}", "warning")

        return redirect(url_for("users.users_list"))

    # --------------------------------------------------
    # GET REQUEST
    # --------------------------------------------------
    return render_template(
        "users_add.html",
        next_employee_id=get_next_employee_id(),
        devices=list_devices(),
    )


# --------------------------------------------------
# Edit user
# --------------------------------------------------
@bp.route("/edit/<employee_id>", methods=["GET", "POST"])
def users_edit(employee_id):
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            "UPDATE users SET name = ? WHERE employee_id = ?",
            (request.form["name"], employee_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("users.users_list"))

    user = cur.execute(
        "SELECT employee_id, name FROM users WHERE employee_id = ?",
        (employee_id,),
    ).fetchone()

    conn.close()
    return render_template("users_edit.html", user=user)

# --------------------------------------------------
# Delete user
# --------------------------------------------------
@bp.route("/delete/<employee_id>", methods=["POST"])
def users_delete(employee_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE employee_id = ?", (employee_id,))
    cur.execute("DELETE FROM device_users WHERE employee_id = ?", (employee_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("users.users_list"))

# --------------------------------------------------
# Weekly hours (HTML)
# --------------------------------------------------
@bp.route("/users/<employee_id>/weekly-hours")
def user_weekly_hours(employee_id):
    week_type = request.args.get("week_type", "mon_sat")
    week_param = request.args.get("week")

    today = datetime.now().date()
    week_start = (
        dtparser.parse(week_param).date()
        if week_param else week_start_for(today, week_type)
    )

    week_end = week_end_for(week_start, week_type)
    week_list = build_week_list(week_type, today)
    week_dates = daterange(week_start, week_end)

    q_start = datetime.combine(week_start - timedelta(days=1), time.min)
    q_end = datetime.combine(week_end + timedelta(days=1), time.max)

    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT employee_id, name, timestamp
        FROM events
        WHERE employee_id = ?
          AND datetime(substr(timestamp,1,19))
              BETWEEN datetime(?) AND datetime(?)
        """,
        (
            employee_id,
            q_start.strftime("%Y-%m-%d %H:%M:%S"),
            q_end.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    ).fetchall()

    conn.close()

    payroll_data = compute_payroll(rows, week_dates)
    report = payroll_data[0] if payroll_data else None

    return render_template(
        "user_weekly_hours.html",
        employee_id=employee_id,
        week_type=week_type,
        week_list=week_list,
        week_start=week_start,
        week_end=week_end,
        week_dates=week_dates,
        report=report,
    )

# --------------------------------------------------
# Weekly hours PDF
# --------------------------------------------------
@bp.route("/users/<employee_id>/weekly-hours/pdf", methods=["GET"])
def user_weekly_hours_pdf(employee_id):
    T = g.T

    WEEKDAYS = [
        T.get("monday", "Monday"),
        T.get("tuesday", "Tuesday"),
        T.get("wednesday", "Wednesday"),
        T.get("thursday", "Thursday"),
        T.get("friday", "Friday"),
        T.get("saturday", "Saturday"),
        T.get("sunday", "Sunday"),
    ]

    week_type = request.args.get("week_type", "mon_sat")
    week_param = request.args.get("week")

    today = datetime.now().date()
    week_start = (
        dtparser.parse(week_param).date()
        if week_param else week_start_for(today, week_type)
    )
    week_end = week_end_for(week_start, week_type)
    week_dates = daterange(week_start, week_end)

    q_start = datetime.combine(week_start - timedelta(days=1), time.min)
    q_end = datetime.combine(week_end + timedelta(days=1), time.max)

    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT employee_id, name, timestamp
        FROM events
        WHERE employee_id = ?
          AND datetime(substr(timestamp,1,19))
              BETWEEN datetime(?) AND datetime(?)
        """,
        (
            employee_id,
            q_start.strftime("%Y-%m-%d %H:%M:%S"),
            q_end.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    ).fetchall()

    conn.close()

    payroll_data = compute_payroll(rows, week_dates)
    report = payroll_data[0] if payroll_data else None
    emp_name = report.name if report and report.name else employee_id

    path = f"/tmp/weekly_hours_{employee_id}_{week_start}.pdf"
    c = canvas.Canvas(path, pagesize=A5)
    width, height = A5
    y = height - 15 * mm

    logo = "/opt/attendance/static/company_logo.png"
    if os.path.exists(logo):
        c.drawImage(logo, 15 * mm, y - 10 * mm, width=30 * mm, preserveAspectRatio=True)
    y -= 15 * mm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, T.get("weekly_hours_report", "Weekly Hours Report"))
    y -= 6 * mm

    c.setFont("Helvetica", 9)
    c.drawString(15 * mm, y, f"{T.get('employee','Employee')}: {emp_name}")
    y -= 5 * mm
    c.drawString(15 * mm, y, f"{T.get('period','Period')}: {week_start} Ã¢ÂÂ {week_end}")
    y -= 8 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(15 * mm, y, T.get("day", "Day"))
    c.drawString(45 * mm, y, T.get("first_in", "In"))
    c.drawString(65 * mm, y, T.get("last_out", "Out"))
    c.drawString(85 * mm, y, T.get("hours", "Hours"))
    c.drawString(105 * mm, y, T.get("overtime", "OT"))
    y -= 4 * mm

    c.setFont("Helvetica", 8)
    for d in week_dates:
        rec = report.days.get(d.isoformat()) if report else None
        label = f"{WEEKDAYS[d.weekday()]} {d.strftime('%d/%m')}"
        c.drawString(15 * mm, y, label)
        c.drawString(45 * mm, y, rec["in"] if rec else "")
        c.drawString(65 * mm, y, rec["out"] if rec else "")
        c.drawRightString(100 * mm, y, rec["hours"] if rec else "00:00")
        c.drawRightString(120 * mm, y, rec["ot"] if rec else "00:00")
        y -= 4 * mm

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15 * mm, y, f"{T.get('regular_hours','Regular')}: {report.total_regular if report else 0}")
    y -= 4 * mm
    c.drawString(15 * mm, y, f"{T.get('overtime_hours','Overtime')}: {report.total_ot if report else 0}")
    y -= 4 * mm
    c.drawString(15 * mm, y, f"{T.get('total_hours','Total')}: {report.total_all if report else 0}")

    y -= 10 * mm
    c.setFont("Helvetica", 8)
    c.drawString(15 * mm, y, T.get("employee_signature", "Employee signature"))
    c.line(15 * mm, y - 2 * mm, 80 * mm, y - 2 * mm)
    c.drawString(90 * mm, y, T.get("date", "Date"))
    c.line(90 * mm, y - 2 * mm, 120 * mm, y - 2 * mm)

    c.showPage()
    c.save()

    return send_file(path, as_attachment=True)

# --------------------------------------------------
# Toggle active / inactive
# --------------------------------------------------
@bp.route("/toggle-active/<employee_id>", methods=["POST"])
def toggle_user_active(employee_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE employee_id = ?
    """, (employee_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("users.users_list"))


def get_users_missing_faces():
    """
    Returns list of employee_id that do not yet have a promoted face.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT u.employee_id
        FROM users u
        LEFT JOIN user_faces f
            ON f.employee_id = u.employee_id
        WHERE f.employee_id IS NULL
    """).fetchall()
    conn.close()

    return [str(r["employee_id"]) for r in rows]


def promote_event_snapshots_for_users(employee_ids):
    """
    Promote best event snapshot to face image for given users.
    """
    if not employee_ids:
        return 0

    conn = get_conn()
    promoted = 0

    for eid in employee_ids:
        row = conn.execute("""
            SELECT image_path
            FROM events
            WHERE employee_id = ?
              AND image_path IS NOT NULL
            ORDER BY confidence DESC, timestamp DESC
            LIMIT 1
        """, (eid,)).fetchone()

        if not row:
            continue

        src = row["image_path"]
        if not os.path.exists(src):
            continue

        dest_dir = "/var/lib/attendance/faces"
        os.makedirs(dest_dir, exist_ok=True)

        dest = os.path.join(dest_dir, f"{eid}.jpg")
        shutil.copyfile(src, dest)

        conn.execute("""
            INSERT OR REPLACE INTO user_faces
            (employee_id, image_path, created_at)
            VALUES (?, ?, datetime('now'))
        """, (eid, dest))

        promoted += 1

    conn.commit()
    conn.close()
    return promoted
