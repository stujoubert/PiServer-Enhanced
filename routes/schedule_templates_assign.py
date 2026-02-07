from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_conn
from authz import login_required, role_required
from services.schedule_templates import list_templates

bp = Blueprint(
    "schedule_templates_assign",
    __name__,
    url_prefix="/schedules"
)

# --------------------------------------------------
# Assign schedules (UI)
# --------------------------------------------------
@bp.route("/assign", methods=["GET"])
@login_required
@role_required("admin")
def schedules_assign_ui():
    conn = get_conn()
    cur = conn.cursor()

    templates = list_templates()

    # IMPORTANT:
    # - UI must use employee_id
    # - Internal joins still use users.id
    users = cur.execute(
        """
        SELECT
            u.employee_id AS employee_id,
            u.name AS name,
            st.name AS current_template
        FROM users u
        LEFT JOIN user_schedule_assignments usa
            ON usa.user_id = u.id
        LEFT JOIN schedule_templates st
            ON st.id = usa.template_id
        ORDER BY
            CASE
                WHEN u.employee_id GLOB '[0-9]*'
                    THEN CAST(u.employee_id AS INTEGER)
                ELSE 999999999
            END,
            u.employee_id
        """
    ).fetchall()

    conn.close()

    return render_template(
        "schedules_assign.html",
        templates=templates,
        users=users,
    )

# --------------------------------------------------
# Assign schedules (POST)
# --------------------------------------------------
@bp.route("/assign", methods=["POST"])
@login_required
@role_required("admin")
def assign_bulk():
    template_id = request.form.get("template_id")  # may be "" to clear
    employee_ids = request.form.getlist("employee_ids")

    if not employee_ids:
        flash("Please select at least one user.", "danger")
        return redirect(url_for("schedule_templates_assign.schedules_assign_ui"))

    conn = get_conn()
    cur = conn.cursor()

    # Resolve employee_id → user_id
    user_ids = [
        row["id"]
        for row in cur.execute(
            f"""
            SELECT id
            FROM users
            WHERE employee_id IN ({",".join("?" * len(employee_ids))})
            """,
            employee_ids,
        ).fetchall()
    ]

    if not user_ids:
        flash("No valid users found.", "danger")
        conn.close()
        return redirect(url_for("schedule_templates_assign.schedules_assign_ui"))

    # Clear assignment if blank
    if not template_id:
        cur.executemany(
            "DELETE FROM user_schedule_assignments WHERE user_id = ?",
            [(uid,) for uid in user_ids],
        )
        conn.commit()
        conn.close()
        flash(f"Cleared template for {len(user_ids)} user(s).", "success")
        return redirect(url_for("schedule_templates_assign.schedules_assign_ui"))

    # Assign template
    cur.executemany(
        """
        INSERT OR REPLACE INTO user_schedule_assignments
            (user_id, template_id, assigned_at)
        VALUES (?, ?, datetime('now'))
        """,
        [(uid, int(template_id)) for uid in user_ids],
    )

    conn.commit()
    conn.close()

    flash(f"Assigned template to {len(user_ids)} user(s).", "success")
    return redirect(url_for("schedule_templates_assign.schedules_assign_ui"))
