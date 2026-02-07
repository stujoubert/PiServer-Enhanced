from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import check_password_hash
import os

bp = Blueprint("auth", __name__, url_prefix="/auth")
DB_PATH = os.getenv("ATT_DB", "/var/lib/attendance/attendance.db")

from db import get_conn

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        conn = get_conn()
        cur = conn.cursor()
        acct = cur.execute(
            "SELECT * FROM accounts WHERE username=? AND active=1",
            (username,)
        ).fetchone()
        conn.close()
        print("DEBUG AUTH:")
        print(" username =", repr(username))
        print(" password =", repr(password))
        print(" acct exists =", bool(acct))
        if acct:
            print(" stored hash =", acct["password_hash"])
            print(" hash check =", check_password_hash(acct["password_hash"], password))
        if not acct or not check_password_hash(acct["password_hash"], password):
            flash("Invalid username or password", "danger")
            return render_template("login.html")

        session.clear()
        session["account_id"] = acct["id"]
        session["role"] = acct["role"]
        session["username"] = acct["username"]
        flash("Logged in", "success")

        return redirect(url_for("dashboard.dashboard"))  # adjust to your dashboard endpoint

    return render_template("login.html")


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
