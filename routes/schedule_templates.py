from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import os

from db import get_conn
from authz import login_required, role_required
from services.schedule_templates import (
    list_templates,
    assign_template_to_user,
)

DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")

bp = Blueprint(
    "schedule_templates",
    __name__,
    url_prefix="/schedules/templates"
)

# --------------------------------------------------
# LIST / CREATE
# --------------------------------------------------

@bp.route("/", methods=["GET"])
@login_required
@role_required("admin")
def templates_page():
    return render_template(
        "schedule_templates.html",
        templates=list_templates(),
    )


@bp.route("/create", methods=["POST"])
@login_required
@role_required("admin")
def create_template():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        flash("Template name is required", "danger")
        return redirect(url_for("schedule_templates.templates_page"))

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO schedule_templates (name, description)
        VALUES (?, ?)
        """,
        (name, description),
    )
    template_id = cur.lastrowid
    conn.commit()
    conn.close()

    return redirect(
        url_for("schedule_templates.edit_template", template_id=template_id)
    )

# --------------------------------------------------
# TEMPLATE EDITOR
# --------------------------------------------------

@bp.route("/<int:template_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_template(template_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute(
            """
            UPDATE schedule_templates
            SET name = ?, description = ?
            WHERE id = ?
            """,
            (
                request.form.get("name", "").strip(),
                request.form.get("description", "").strip(),
                template_id,
            ),
        )
        conn.commit()

    template = cur.execute(
        "SELECT * FROM schedule_templates WHERE id = ?",
        (template_id,),
    ).fetchone()

    rules_raw = cur.execute(
        """
        SELECT *
        FROM schedule_rules
        WHERE template_id = ?
        ORDER BY id
        """,
        (template_id,),
    ).fetchall()

    rules = []
    for r in rules_raw:
        shifts = cur.execute(
            """
            SELECT *
            FROM schedule_shifts
            WHERE rule_id = ?
            ORDER BY start_time
            """,
            (r["id"],),
        ).fetchall()

        rules.append({
            **dict(r),
            "shifts": [dict(s) for s in shifts],
        })

    conn.close()

    return render_template(
        "schedule_template_edit.html",
        template=dict(template),
        rules=rules,
    )

# --------------------------------------------------
# RULES
# --------------------------------------------------

@bp.route("/<int:template_id>/rules/add", methods=["POST"])
@login_required
@role_required("admin")
def add_rule(template_id):
    days = request.form.getlist("weekdays[]")
    priority = int(request.form.get("priority", 0))

    if not days:
        flash("Weekdays are required", "danger")
        return redirect(
            url_for("schedule_templates.edit_template", template_id=template_id)
        )

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO schedule_rules (template_id, weekdays, priority)
        VALUES (?, ?, ?)
        """,
        (template_id, ",".join(days), priority),
    )

    conn.commit()
    conn.close()

    from services.schedule_templates import rebuild_template_days
    rebuild_template_days(template_id)

    flash("Rule added.", "success")
    return redirect(
        url_for("schedule_templates.edit_template", template_id=template_id)
    )

@bp.route("/rules/<int:rule_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_rule(rule_id):
    conn = get_conn()

    row = conn.execute(
        "SELECT template_id FROM schedule_rules WHERE id = ?",
        (rule_id,)
    ).fetchone()

    if row:
        template_id = row["template_id"]

        conn.execute("DELETE FROM schedule_shifts WHERE rule_id = ?", (rule_id,))
        conn.execute("DELETE FROM schedule_rules WHERE id = ?", (rule_id,))
        conn.commit()

        from services.schedule_templates import rebuild_template_days
        rebuild_template_days(template_id)

    conn.close()

    flash("Rule deleted", "warning")
    return redirect(request.referrer or url_for("schedule_templates.templates_page"))

# --------------------------------------------------
# SHIFTS
# --------------------------------------------------

@bp.route("/rule/<int:rule_id>/shift", methods=["POST"])
@login_required
@role_required("admin")
def add_shift(rule_id):
    conn = get_conn()

    row = conn.execute(
        "SELECT template_id FROM schedule_rules WHERE id = ?",
        (rule_id,),
    ).fetchone()

    if not row:
        conn.close()
        flash("Rule not found", "danger")
        return redirect(url_for("schedule_templates.templates_page"))

    conn.execute(
        """
        INSERT INTO schedule_shifts
            (rule_id, start_time, end_time, grace_minutes, break_minutes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            rule_id,
            request.form.get("start_time"),
            request.form.get("end_time"),
            int(request.form.get("grace_minutes", 0)),
            int(request.form.get("break_minutes", 0)),
        ),
    )

    conn.commit()

    from services.schedule_templates import rebuild_template_days
    rebuild_template_days(row["template_id"])

    conn.close()

    return redirect(
        url_for("schedule_templates.edit_template", template_id=row["template_id"])
    )

@bp.route("/shift/<int:shift_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_shift(shift_id):
    conn = get_conn()
    row = conn.execute(
        """
        SELECT r.template_id
        FROM schedule_shifts s
        JOIN schedule_rules r ON r.id = s.rule_id
        WHERE s.id = ?
        """,
        (shift_id,),
    ).fetchone()

    if row:
        conn.execute("DELETE FROM schedule_shifts WHERE id = ?", (shift_id,))
        conn.commit()

        from services.schedule_templates import rebuild_template_days
        rebuild_template_days(template_id)


    conn.close()
    return redirect(
        url_for("schedule_templates.edit_template", template_id=row["template_id"])
    )

# --------------------------------------------------
# ASSIGN SINGLE USER
# --------------------------------------------------
@bp.route("/assign", methods=["POST"])
@login_required
@role_required("admin")
def assign_template():
    employee_id = request.form.get("employee_id")
    template_id = request.form.get("template_id")

    if not employee_id or not template_id:
        return redirect(url_for("schedule_templates.templates_page"))

    conn = get_conn()
    cur = conn.cursor()

    user = cur.execute(
        "SELECT id FROM users WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()

    if user:
        cur.execute(
            """
            INSERT OR REPLACE INTO user_schedule_assignments
                (user_id, template_id, assigned_at)
            VALUES (?, ?, datetime('now'))
            """,
            (user["id"], int(template_id)),
        )

    conn.commit()
    conn.close()

    flash("Schedule assigned", "success")
    return redirect(url_for("schedule_templates.templates_page"))



# --------------------------------------------------
# PREVIEW
# --------------------------------------------------

@bp.route("/<int:template_id>/weekly")
@login_required
@role_required("admin")
def weekly_preview(template_id):
    from advanced_schedules import build_weekly_grid

    conn = get_conn()
    template = conn.execute(
        "SELECT * FROM schedule_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    conn.close()

    grid = build_weekly_grid(template_id)

    return render_template(
        "schedule_template_weekly.html",
        template=template,
        grid=grid,
    )

@bp.route("/assign-bulk", methods=["POST"])
@login_required
@role_required("admin")
def assign_template_bulk():
    template_id = request.form.get("template_id")
    employee_ids = request.form.getlist("employee_ids[]")

    if not template_id or not employee_ids:
        flash("Select template and users", "danger")
        return redirect(url_for("schedule_templates.templates_page"))

    conn = get_conn()
    cur = conn.cursor()

    for emp_id in employee_ids:
        row = cur.execute(
            "SELECT id FROM users WHERE employee_id = ?",
            (emp_id,)
        ).fetchone()
        if not row:
            continue

        cur.execute(
            """
            INSERT OR REPLACE INTO user_schedule_assignments
                (user_id, template_id, assigned_at)
            VALUES (?, ?, datetime('now'))
            """,
            (row["id"], int(template_id)),
        )

    conn.commit()
    conn.close()

    flash("Templates assigned", "success")
    return redirect(url_for("schedule_templates.templates_page"))
