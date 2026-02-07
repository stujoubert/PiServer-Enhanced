from flask import Blueprint, send_file, request
from services.reports import export_fifo_excel
from datetime import datetime, timedelta

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/export_fifo")
def export_fifo():
    week_type = request.args.get("week_type", "mon_sat")
    week_param = request.args.get("week")

    today = datetime.now().date()

    if week_param:
        week_start = datetime.fromisoformat(week_param).date()
    else:
        # fallback (should not happen if coming from payroll page)
        week_start = today - timedelta(days=today.weekday())

    # SAME logic as payroll
    if week_type == "mon_sat":
        week_end = week_start + timedelta(days=5)
    elif week_type == "sat_fri":
        week_end = week_start + timedelta(days=6)
    elif week_type == "sun_sat":
        week_end = week_start + timedelta(days=6)
    else:
        week_end = week_start + timedelta(days=5)

    output = "/tmp/fifo_attendance.xlsx"
    export_fifo_excel(
        output,
        start_date=week_start.isoformat(),
        end_date=week_end.isoformat(),
    )

    return send_file(
        output,
        as_attachment=True,
        download_name="fifo_attendance.xlsx"
    )
