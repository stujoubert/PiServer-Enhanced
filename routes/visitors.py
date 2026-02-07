# routes/visitors.py

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from authz import login_required, role_required
from db import get_conn

from services.visitor_passes import (
    create_visitor_pass,
    revoke_visitor_pass,
    list_visitor_passes,
    get_visitor_pass,
    get_visitor_events,
    generate_visitor_employee_no,
)

bp = Blueprint("visitors", __name__, url_prefix="/visitors")


# -------------------------------------------------
# Visitor Logbook
# -------------------------------------------------
@bp.route("/", methods=["GET"])
@login_required
@role_required("admin", "manager")
def visitors_logbook():
    passes = list_visitor_passes()
    return render_template("visitors_logbook.html", passes=passes)


# -------------------------------------------------
# New Visitor Pass
# -------------------------------------------------
@bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "manager")
def visitors_new():
    if request.method == "POST":
        visitor_name = request.form["visitor_name"].strip()
        device_id = int(request.form["device_id"])
        valid_until = request.form["valid_until"]

        if not visitor_name or not valid_until:
            flash("Visitor name and expiration are required.", "danger")
            return redirect(url_for("visitors.visitors_new"))

        conn = get_conn()
        visitor_employee_no = generate_visitor_employee_no(conn)
        conn.close()

        issued_by_employee_id = session.get("employee_id", "system")

        vp_id = create_visitor_pass(
            visitor_name=visitor_name,
            visitor_employee_no=visitor_employee_no,
            device_id=device_id,
            valid_until=valid_until,
            issued_by_employee_id=issued_by_employee_id,
        )

        flash("Visitor pass created", "success")
        return redirect(url_for("visitors.visitor_view", visitor_id=vp_id))

    conn = get_conn()
    devices = conn.execute(
        "SELECT id, name FROM devices ORDER BY name"
    ).fetchall()
    conn.close()

    return render_template("visitor_new.html", devices=devices)


# -------------------------------------------------
# View Visitor Pass
# -------------------------------------------------
@bp.route("/<int:visitor_id>", methods=["GET"])
@login_required
@role_required("admin", "manager")
def visitor_view(visitor_id):
    vp = get_visitor_pass(visitor_id)
    if not vp:
        flash("Visitor not found", "danger")
        return redirect(url_for("visitors.visitors_logbook"))

    events = get_visitor_events(visitor_id)

    return render_template(
        "visitor_view.html",
        vp=vp,
        visitor=vp,
        events=events,
    )


# -------------------------------------------------
# Revoke Visitor Pass
# -------------------------------------------------
@bp.route("/<int:visitor_id>/revoke", methods=["POST"])
@login_required
@role_required("admin", "manager")
def visitors_revoke(visitor_id):
    reason = request.form.get("reason", "")
    revoked_by = session.get("employee_id", "system")

    revoke_visitor_pass(
        visitor_id=visitor_id,
        revoked_by=revoked_by,
        reason=reason,
    )

    flash("Visitor pass revoked", "warning")
    return redirect(url_for("visitors.visitor_view", visitor_id=visitor_id))
