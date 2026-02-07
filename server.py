#!/usr/bin/env python3
# server.py — FULL DROP-IN REPLACEMENT
# Nothing should appear above this line

import os
import sys

# --------------------------------------------------
# Environment safety guard (SINGLE SOURCE OF TRUTH)
# --------------------------------------------------
ATT_ENV = os.environ.get("ATT_ENV", "prod")
ATT_DB = os.environ.get("ATT_DB")

if not ATT_DB:
    raise RuntimeError("ATT_DB is not set — refusing to start")

print(">>> USING DATABASE:", ATT_DB)

if ATT_ENV == "dev" and "/var/lib/attendance/" in ATT_DB:
    raise RuntimeError(
        "DEV environment pointing at PROD database — refusing to start"
    )

print("=== LOADED SERVER.PY FROM /opt/attendance/server.py ===")

# --------------------------------------------------
# Path setup
# --------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# --------------------------------------------------
# Database bootstrap (idempotent, safe)
# --------------------------------------------------
from scripts.bootstrap_db import main as bootstrap_db
bootstrap_db()

# --------------------------------------------------
# Flask app setup
# --------------------------------------------------
from flask import Flask, redirect, url_for

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)

app.secret_key = os.getenv("SECRET_KEY", "change_me")
print("SECRET_KEY =", app.secret_key)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB

# --------------------------------------------------
# i18n initialization (SINGLE SOURCE OF TRUTH)
# --------------------------------------------------
from translations import init_i18n
init_i18n(app)

# --------------------------------------------------
# Jinja filters
# --------------------------------------------------
def translate_weekdays(value, T):
    """
    Converts '0,1,2' -> 'Monday, Tuesday, Wednesday'
    using translation keys (weekday_0 .. weekday_6)
    """
    if not value:
        return ""

    days = []
    for d in value.split(","):
        key = f"weekday_{d.strip()}"
        days.append(T.get(key, d))

    return ", ".join(days)

app.jinja_env.filters["translate_weekdays"] = translate_weekdays

# --------------------------------------------------
# Global template context (company settings)
# --------------------------------------------------
@app.context_processor
def inject_company():
    try:
        from services.settings import get_company_settings
        return {"company": get_company_settings()}
    except Exception:
        # Never break page rendering due to settings issues
        return {"company": {"name": "", "rfc": "", "logo_path": ""}}

# --------------------------------------------------
# Root route
# --------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard.dashboard"))

# --------------------------------------------------
# Blueprint registration helper
# --------------------------------------------------
def register(bp, name):
    app.register_blueprint(bp)
    print(f"[OK] Registered {name}")

# --------------------------------------------------
# Blueprints (ORDER PRESERVED)
# --------------------------------------------------
from routes.users import bp as users_bp
register(users_bp, "routes.users")

from routes.devices import bp as devices_bp
register(devices_bp, "routes.devices")

from routes.daily import bp as daily_bp
register(daily_bp, "routes.daily")

from routes.weekly import bp as weekly_bp
register(weekly_bp, "routes.weekly")

from routes.schedule_templates import bp as schedule_templates_bp
register(schedule_templates_bp, "routes.schedule_templates")

from routes.payroll import bp as payroll_bp
register(payroll_bp, "routes.payroll")

from routes.daily_audit import bp as daily_audit_bp
register(daily_audit_bp, "routes.daily_audit")

from routes.reports import bp as reports_bp
register(reports_bp, "routes.reports")

from routes.dashboard import bp as dashboard_bp
register(dashboard_bp, "routes.dashboard")

from routes.auth import bp as auth_bp
register(auth_bp, "routes.auth")

from routes.accounts import bp as accounts_bp
register(accounts_bp, "routes.accounts")

from routes.company import bp as company_bp
app.register_blueprint(company_bp)

from routes.schedule_templates_assign import bp as schedule_templates_assign_bp
app.register_blueprint(schedule_templates_assign_bp)

from routes.device_users import bp as device_users_bp
app.register_blueprint(device_users_bp)

from routes.visitors import bp as visitors_bp
app.register_blueprint(visitors_bp)

# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("ATT_PORT", "5000")),
        debug=False,
    )
