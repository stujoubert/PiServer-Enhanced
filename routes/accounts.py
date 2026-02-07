from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
from werkzeug.security import generate_password_hash
from authz import login_required, role_required
import os

bp = Blueprint("accounts", __name__, url_prefix="/accounts")
DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@bp.route("/")
@login_required
@role_required("admin")
def accounts_list():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, active FROM accounts ORDER BY username"
    ).fetchall()
    conn.close()

    return render_template("accounts.html", accounts=rows)

@bp.route("/create", methods=["POST"])
@login_required
@role_required("admin")
def accounts_create():
    username = request.form.get("username", "").strip()
    role = request.form.get("role")
    password = request.form.get("password")

    if not username or not password or role not in ("admin","manager","viewer"):
        flash("Invalid input", "danger")
        return redirect(url_for("accounts.accounts_list"))

    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO accounts (username, password_hash, role, active)
            VALUES (?, ?, ?, 1)
        """, (username, generate_password_hash(password), role))
        conn.commit()
        flash("Account created", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists", "danger")
    finally:
        conn.close()

    return redirect(url_for("accounts.accounts_list"))

@bp.route("/reset/<int:account_id>", methods=["POST"])
@login_required
@role_required("admin")
def accounts_reset(account_id):
    new_password = request.form.get("password")

    if not new_password:
        flash("Password required", "danger")
        return redirect(url_for("accounts.accounts_list"))

    conn = get_conn()
    conn.execute("""
        UPDATE accounts
        SET password_hash=?
        WHERE id=?
    """, (generate_password_hash(new_password), account_id))
    conn.commit()
    conn.close()

    flash("Password reset", "success")
    return redirect(url_for("accounts.accounts_list"))

@bp.route("/toggle/<int:account_id>", methods=["POST"])
@login_required
@role_required("admin")
def accounts_toggle(account_id):
    # Prevent admin from deactivating themselves
    if session.get("account_id") == account_id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("accounts.accounts_list"))

    conn = get_conn()
    conn.execute("""
        UPDATE accounts
        SET active = CASE active WHEN 1 THEN 0 ELSE 1 END
        WHERE id=?
    """, (account_id,))
    conn.commit()
    conn.close()

    flash("Account status updated", "success")
    return redirect(url_for("accounts.accounts_list"))

