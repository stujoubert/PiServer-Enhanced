from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from datetime import datetime
from db import get_conn
from collector import fetch_from_device

from authz import login_required, role_required

bp = Blueprint("devices", __name__)



# ------------------------------------------------------
# ADD DEVICE (RESTORED)
# ------------------------------------------------------
@bp.route("/devices/add", methods=["POST"])
def device_add():
    name = request.form.get("name")
    ip = request.form.get("ip")
    username = request.form.get("username", "admin")
    password = request.form.get("password", "")
    active = 1

    if not name or not ip:
        flash("Device name and IP are required", "error")
        return redirect(url_for("devices.devices_page"))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO devices (name, ip, username, password, active)
        VALUES (?, ?, ?, ?, ?)
    """, (name, ip, username, password, active))

    conn.commit()
    conn.close()

    flash("Device added successfully", "success")
    return redirect(url_for("devices.devices_page"))


# ------------------------------------------------------
# DEVICES PAGE
# ------------------------------------------------------
@bp.route("/devices/")
@login_required
@role_required("admin")
def devices_page():
    conn = get_conn()
    cur = conn.cursor()

    devices = cur.execute("""
        SELECT
            id,
            name,
            ip,
            active,
            last_fetch_at,
            last_fetch_count
        FROM devices
        ORDER BY name
    """).fetchall()

    conn.close()
    return render_template("devices.html", devices=devices)


# ------------------------------------------------------
# FETCH NOW (FIXED)
# ------------------------------------------------------
@bp.route("/devices/<int:device_id>/fetch_now")
def device_fetch_now(device_id):
    conn = get_conn()
    cur = conn.cursor()

    device = cur.execute(
        "SELECT ip, username, password FROM devices WHERE id = ?",
        (device_id,)
    ).fetchone()

    conn.close()

    if not device:
        flash("Device not found", "error")
        return redirect(url_for("devices.devices_page"))

    fetch_from_device(
        device["ip"],
        device["username"],
        device["password"],
        device_id=device_id,
        start=None,
        end=None
    )

    flash("Fetch completed", "success")
    return redirect(url_for("devices.devices_page"))


# ------------------------------------------------------
# TOGGLE DEVICE
# ------------------------------------------------------
@bp.route("/devices/<int:device_id>/toggle", methods=["POST"])
def device_toggle(device_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE devices
        SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END
        WHERE id = ?
    """, (device_id,))

    conn.commit()
    conn.close()

    flash("Device status updated", "success")
    return redirect(url_for("devices.devices_page"))


# ------------------------------------------------------
# DELETE DEVICE
# ------------------------------------------------------
@bp.route("/devices/<int:device_id>/delete", methods=["POST"])
def device_delete(device_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()
    conn.close()

    flash("Device deleted", "success")
    return redirect(url_for("devices.devices_page"))

# ------------------------------------------------------
# EDIT DEVICE
# ------------------------------------------------------

@bp.route("/edit/<int:device_id>", methods=["GET", "POST"])
def device_edit(device_id):
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE devices
            SET
                name = ?,
                ip = ?,
                username = ?,
                password = ?,
                active = ?,
                supports_fdlib = ?
            WHERE id = ?
        """, (
            request.form["name"],
            request.form["ip"],
            request.form.get("username"),
            request.form.get("password"),
            int(request.form.get("active", 1)),
            int(request.form.get("supports_fdlib", 0)),
            device_id,
        ))
        conn.commit()
        conn.close()

        flash("Device updated successfully.", "success")
        return redirect(url_for("devices.devices_page"))

    device = cur.execute("""
        SELECT
            id,
            name,
            ip,
            username,
            password,
            active,
            supports_fdlib
        FROM devices
        WHERE id = ?
    """, (device_id,)).fetchone()

    conn.close()

    if not device:
        flash("Device not found", "danger")
        return redirect(url_for("devices.devices_page"))

    return render_template(
        "edit_device.html",
        device=device,
    )

